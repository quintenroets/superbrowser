import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from superbrowser import Browser

COOKIE = {"name": "session", "value": "secret"}
FOREIGN_COOKIE = {"name": "foreign", "value": "other", "domain": "example.com"}


class EmptyPageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()


@pytest.fixture
def url() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), EmptyPageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


def test_browser_without_root_url() -> None:
    with Browser() as browser:
        assert browser.root_url is None


@pytest.mark.parametrize(
    "cookies",
    [[COOKIE], [FOREIGN_COOKIE, COOKIE]],
    ids=["own_domain", "foreign_cookie_does_not_discard_others"],
)
def test_cookies_round_trip(url: str, cookies: list[dict[str, str]]) -> None:
    with Browser(root_url=url, cookies=cookies) as browser:
        extracted_cookies = browser.extract_cookies()
    values = {cookie["name"]: cookie["value"] for cookie in extracted_cookies}
    assert values == {COOKIE["name"]: COOKIE["value"]}


class BrokenBrowser(Browser):
    def setup_session(self) -> None:
        raise RuntimeError


def test_setup_failure_quits_driver() -> None:
    browser = BrokenBrowser()
    with pytest.raises(RuntimeError), browser:
        pass  # pragma: no cover
    assert not browser.service.is_connectable()
