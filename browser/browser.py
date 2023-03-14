from dataclasses import dataclass, field

from plib import Path
from selenium.common import exceptions as exc
from selenium.webdriver import Chrome, ChromeOptions


@dataclass
class Browser(Chrome):
    root_url: str = None
    cookies_path: Path = None
    headless: bool = False
    options: list = field(default_factory=list)
    experimental_options: dict = field(default_factory=dict)

    @property
    def saved_cookies(self) -> dict | None:
        return self.cookies_path and self.cookies_path.yaml

    @saved_cookies.setter
    def saved_cookies(self, value):
        if self.cookies_path is not None:
            self.cookies_path.encrypted.yaml = value

    def __enter__(self):
        self.initialize()
        super().__init__()
        self.load_root_url()
        self.root_url = self.current_url  # standardized version
        self.load_cookies()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_cookies()
        super().__exit__(exc_type, exc_val, exc_tb)
        self.quit()

    def initialize(self):
        options = self.options + ["start-maximized"]
        if self.headless:
            options.append("headless")

        browser_options = ChromeOptions()
        for option in options:
            browser_options.add_argument(f"--{option}")
        for name, value in self.experimental_options:
            browser_options.add_experimental_option(name, value)

    def load_root_url(self, reload=False):
        if self.root_url:
            if reload or self.current_url != self.root_url:
                self.get(self.root_url)

    def load_cookies(self):
        cookies = self.saved_cookies
        if cookies is not None:
            self.add_cookies(cookies)
            self.load_root_url(reload=True)

    def add_cookies(self, cookies):
        for cookie in cookies:
            try:
                self.add_cookie(cookie)
            except exc.InvalidCookieDomainException:
                pass

    def save_cookies(self):
        if self.cookies_path is not None:
            self.load_root_url()
            self.saved_cookies = self.get_cookies()
