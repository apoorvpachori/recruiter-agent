from collections.abc import Iterator

import httpx
import pytest

from recruiter_agent.tools.read_webpage import get_page_url


class MockResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content: bytes = b"",
        url: str = "https://example.com/jobs/role",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}
        self.content = content
        self.url = httpx.URL(url)
        self.encoding = "utf-8"
        self.is_redirect = status_code in {301, 302, 303, 307, 308}

    def __enter__(self) -> MockResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def iter_bytes(self) -> Iterator[bytes]:
        yield self.content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("request failed", request=None, response=None)


class MockClient:
    def __init__(self, responses: list[MockResponse]) -> None:
        self.responses = iter(responses)
        self.requests: list[str] = []

    def __enter__(self) -> MockClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def stream(self, method: str, url: str) -> MockResponse:
        assert method == "GET"
        self.requests.append(url)
        response = next(self.responses)
        response.url = httpx.URL(url)
        return response


def test_extracts_main_page_content(monkeypatch: pytest.MonkeyPatch) -> None:
    html = b"""<html><head><title>Applied AI Engineer</title>
    <meta name="description" content="Build AI systems"></head>
    <body><header>Header</header><main><h1>Role</h1><p>Build agents.</p>
    <script>ignore me</script></main><footer>Footer</footer></body></html>"""
    client = MockClient([MockResponse(content=html)])
    monkeypatch.setattr("recruiter_agent.tools.read_webpage.httpx.Client", lambda **_: client)
    monkeypatch.setattr(
        "recruiter_agent.tools.read_webpage._validate_public_http_url", lambda _: None
    )

    page = get_page_url("https://example.com/jobs/role")

    assert page.title == "Applied AI Engineer"
    assert page.description == "Build AI systems"
    assert page.text == "Role Build agents."
    assert page.final_url == "https://example.com/jobs/role"
    assert "ignore me" not in page.text


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


def test_redirect_destination_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    redirect = MockResponse(
        status_code=302,
        headers={"location": "http://127.0.0.1/admin"},
        url="https://example.com/jobs/role",
    )
    client = MockClient([redirect])
    monkeypatch.setattr("recruiter_agent.tools.read_webpage.httpx.Client", lambda **_: client)
    validated: list[str] = []

    def validate(url: str) -> None:
        validated.append(url)
        if "127.0.0.1" in url:
            raise ValueError("Private or non-public network addresses are not supported.")

    monkeypatch.setattr("recruiter_agent.tools.read_webpage._validate_public_http_url", validate)

    with pytest.raises(ValueError, match="Private or non-public"):
        get_page_url("https://example.com/jobs/role")

    assert len(validated) == 2
    assert len(client.requests) == 1
