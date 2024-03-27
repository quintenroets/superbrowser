import time
import typing
import urllib.parse
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import cached_property
from types import TracebackType

from selenium.common import exceptions as exc
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support import ui
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from superpathlib import Path


@dataclass
class Browser(Chrome):
    root_url: str | None = None
    cookies_path: Path | None = None
    headless: bool = True
    options: list[str] = field(default_factory=list)
    experimental_options: dict[str, str] = field(default_factory=dict)
    timeout: int = 10
    sleep_interval: int = 2
    page_load_locator: tuple[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.page_load_locator = (By.TAG_NAME, "body")

    @property
    def login_locator(self) -> tuple[str, str]:
        raise NotImplementedError

    @property
    def saved_cookies(self) -> list[dict[str, str]] | None:
        return (
            None
            if self.cookies_path is None
            else typing.cast(list[dict[str, str]], self.cookies_path.yaml)
        )

    @saved_cookies.setter
    def saved_cookies(self, value: list[dict[str, str]]) -> None:
        if self.cookies_path is not None:
            self.cookies_path.encrypted.yaml = value

    @cached_property
    def waiter(self) -> ui.WebDriverWait[Chrome]:
        return ui.WebDriverWait(self, self.timeout)

    def __enter__(self) -> None:
        self.initialize()
        self.load_root_url()
        self.root_url = self.current_url  # standardized version
        self.load_cookies()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> None:
        if not exception_type:
            self.save_cookies()
        self.close()
        self.quit()
        super().__exit__(exception_type, exception_value, exception_traceback)

    def initialize(self) -> None:
        browser_options = ChromeOptions()
        for option in self.generate_options():
            browser_options.add_argument(option)
        for name, value in self.experimental_options.items():
            browser_options.add_experimental_option(name, value)
        super().__init__(options=browser_options)

    def generate_options(self) -> Iterator[str]:
        yield from self.options
        yield "start-maximized"
        if self.headless:
            yield "headless"

    def load_root_url(self, reload: bool = False) -> None:
        if self.root_url:
            if reload or self.current_url != self.root_url:
                self.get(self.root_url)

    def load_cookies(self) -> None:
        cookies = self.saved_cookies
        if cookies is not None:
            self.add_cookies(cookies)
            self.load_root_url(reload=True)

    def add_cookies(self, cookies: list[dict[str, str]]) -> None:
        for cookie in cookies:
            try:
                self.add_cookie(cookie)
            except exc.InvalidCookieDomainException:
                pass

    def save_cookies(self) -> None:
        if self.cookies_path is not None:
            self.load_root_url()
            self.saved_cookies = self.get_cookies()

    def wait_for_page_load(
        self, page_load_locator: tuple[str, str] | None = None
    ) -> None:
        if page_load_locator is None:
            page_load_locator = self.page_load_locator
        self.wait_for_element(page_load_locator)

    def wait_for_element(self, locator: tuple[str, str]) -> None:
        condition = presence_of_element_located(locator)
        self.wait_for(condition)

    def wait_for(self, condition: Callable[[WebDriver], WebElement]) -> None:
        self.waiter.until(condition)

    def check_login(self) -> None:
        if not self.is_logged_in():
            self.login()

    def is_present(self, by: str = By.ID, value: str | None = None) -> bool:
        try:
            self.find_element(by, value)
            is_present = True
        except exc.NoSuchElementException:
            is_present = False
        return is_present

    def is_logged_in(self) -> bool:
        return not self.is_present(*self.login_locator)

    def login(self) -> None:
        self.click_login()

    def click_login(self) -> None:
        self.login_button.click()

    @property
    def login_button(self) -> WebElement:
        return self.find_element(*self.login_locator)

    def get(self, url: str, wait_for_load: bool = False) -> None:
        if not self.is_absolute(url):
            root_url = typing.cast(str, self.root_url)
            url = urllib.parse.urljoin(root_url, url)
        super().get(url)
        if wait_for_load:
            self.wait_for_page_load()

    @classmethod
    def is_absolute(cls, url: str) -> bool:
        schemes = "http", "https"
        return any(url.startswith(scheme) for scheme in schemes)

    def sleep(self) -> None:
        time.sleep(self.sleep_interval)
