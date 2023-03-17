import time
import urllib.parse
from dataclasses import dataclass, field
from functools import cached_property

from plib import Path
from selenium.common import exceptions as exc
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import ui
from selenium.webdriver.support.expected_conditions import presence_of_element_located


@dataclass
class Browser(Chrome):
    root_url: str = None
    cookies_path: Path = None
    headless: bool = True
    options: list = field(default_factory=list)
    experimental_options: dict = field(default_factory=dict)
    timeout: int = 10
    sleep_interval: int = 2

    def __post_init__(self):
        self.page_load_locator = (By.TAG_NAME, "body")

    @property
    def login_locator(self):
        raise NotImplementedError

    @property
    def saved_cookies(self) -> dict | None:
        return self.cookies_path and self.cookies_path.yaml

    @saved_cookies.setter
    def saved_cookies(self, value):
        if self.cookies_path is not None:
            self.cookies_path.encrypted.yaml = value

    @cached_property
    def waiter(self):
        return ui.WebDriverWait(self, self.timeout)

    def __enter__(self):
        self.initialize()
        self.load_root_url()
        self.root_url = self.current_url  # standardized version
        self.load_cookies()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.save_cookies()
        self.close()
        self.quit()
        super().__exit__(exc_type, exc_val, exc_tb)

    def initialize(self):
        options = self.options + ["start-maximized"]
        if self.headless:
            options.append("headless")

        browser_options = ChromeOptions()
        for option in options:
            browser_options.add_argument(option)
        for name, value in self.experimental_options:
            browser_options.add_experimental_option(name, value)
        super().__init__(options=browser_options)

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

    def wait_for_page_load(self, page_load_locator=None):
        if page_load_locator is None:
            page_load_locator = self.page_load_locator
        self.wait_for_element(page_load_locator)

    def wait_for_element(self, locator):
        condition = presence_of_element_located(locator)
        self.wait_for(condition)

    def wait_for(self, condition):
        self.waiter.until(condition)

    def check_login(self):
        if not self.is_logged_in():
            self.login()

    def is_present(self, by=By.ID, value: str | None = None) -> bool:
        try:
            self.find_element(by, value)
            is_present = True
        except exc.NoSuchElementException:
            is_present = False
        return is_present

    def is_logged_in(self):
        return not self.is_present(*self.login_locator)

    def login(self):
        self.click_login()

    def click_login(self):
        self.login_button.click()

    @property
    def login_button(self):
        return self.find_element(*self.login_locator)

    def get(self, url, wait_for_load=False):
        if not self.is_absolute(url):
            url = urllib.parse.urljoin(self.root_url, url)
        super().get(url)
        if wait_for_load:
            self.wait_for_page_load()

    @classmethod
    def is_absolute(cls, url):
        return any(url.startswith(scheme) for scheme in ("http", "https"))

    def sleep(self):
        time.sleep(self.sleep_interval)
