import asyncio

import pytest

from recruiter_agent.tools.read_webpage import get_page_url


class MockBrowserContext:
    def __init__(self, page) -> None:
        self.page = page
        self.route_handler = None
        self.closed = False

    async def route(self, pattern, handler) -> None:
        self.route_handler = handler

    async def new_page(self):
        return self.page

    async def close(self) -> None:
        self.closed = True


class MockBrowser:
    def __init__(self, context) -> None:
        self.context = context
        self.closed = False

    async def new_context(self, **kwargs):
        return self.context

    async def close(self) -> None:
        self.closed = True


class MockChromium:
    def __init__(self, browser) -> None:
        self.browser = browser

    async def launch(self, **kwargs):
        return self.browser


class MockPlaywright:
    def __init__(self, chromium) -> None:
        self.chromium = chromium


class MockPlaywrightManager:
    def __init__(self, playwright) -> None:
        self.playwright = playwright

    async def __aenter__(self):
        return self.playwright

    async def __aexit__(self, *_):
        return None


class MockLocator:
    def __init__(self, text=None, attribute=None) -> None:
        self.text = text
        self.attribute = attribute

    async def get_attribute(self, name, timeout=None):
        return self.attribute

    async def inner_text(self, timeout=None):
        return self.text


class MockPage:
    def __init__(self, *, title, description, text, url):
        self._title = title
        self._description = description
        self._text = text
        self.url = url

    async def goto(self, url, *, wait_until, timeout):
        class Response:
            status = 200

        return Response()

    async def wait_for_load_state(self, state, timeout=None):
        return None

    async def title(self):
        return self._title

    def locator(self, selector):
        if selector.startswith("meta"):
            return MockLocator(attribute=self._description)
        return MockLocator(text=self._text)


def test_extracts_main_page_content(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MockPage(
        title="Applied AI Engineer",
        description="Build AI systems",
        text="Role\nBuild agents.",
        url="https://example.com/jobs/role",
    )
    context = MockBrowserContext(page)
    browser = MockBrowser(context)
    playwright = MockPlaywright(MockChromium(browser))
    monkeypatch.setattr(
        "recruiter_agent.tools.read_webpage.async_playwright",
        lambda: MockPlaywrightManager(playwright),
    )
    monkeypatch.setattr(
        "recruiter_agent.tools.read_webpage._validate_public_http_url", lambda _: None
    )

    page = get_page_url("https://example.com/jobs/role")

    assert page.title == "Applied AI Engineer"
    assert page.description == "Build AI systems"
    assert page.text == "Role Build agents."
    assert page.final_url == "https://example.com/jobs/role"
    assert context.closed
    assert browser.closed


def test_rejects_non_http_and_local_urls() -> None:
    with pytest.raises(ValueError, match="HTTP and HTTPS"):
        get_page_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="Localhost"):
        get_page_url("http://localhost/admin")
    with pytest.raises(ValueError, match="credentials"):
        get_page_url("https://user:pass@example.com/job")


def test_rejects_private_ip_addresses() -> None:
    with pytest.raises(ValueError, match="Private or non-public"):
        get_page_url("http://127.0.0.1/internal")


def test_rejects_custom_ports() -> None:
    with pytest.raises(ValueError, match="Custom ports"):
        get_page_url("https://example.com:8443/job")


def test_navigation_route_rejects_private_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MockPage(title="Role", description=None, text="text", url="https://example.com/job")
    context = MockBrowserContext(page)
    browser = MockBrowser(context)
    playwright = MockPlaywright(MockChromium(browser))
    monkeypatch.setattr(
        "recruiter_agent.tools.read_webpage.async_playwright",
        lambda: MockPlaywrightManager(playwright),
    )
    monkeypatch.setattr(
        "recruiter_agent.tools.read_webpage._validate_public_http_url",
        lambda url: (_ for _ in ()).throw(ValueError("private")) if "127.0.0.1" in url else None,
    )

    get_page_url("https://example.com/jobs/role")
    Route = type("Route", (), {"request": type("Request", (), {"url": "http://127.0.0.1/admin"})()})
    action = {"aborted": False}

    async def abort(self):
        action["aborted"] = True

    async def continue_route(self):
        action["continued"] = True

    Route.abort = abort
    Route.continue_ = continue_route
    asyncio.run(context.route_handler(Route()))
    assert action["aborted"] is True
