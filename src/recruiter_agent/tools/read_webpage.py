"""Read-only webpage retrieval and text extraction."""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

MAX_RESPONSE_BYTES = 2_000_000
MAX_TEXT_CHARS = 30_000
MAX_REDIRECTS = 5
USER_AGENT = "recruiter-agent/0.1 (read-only job research)"


class PageContent(BaseModel):
    """Bounded, plain-text content and metadata extracted from a webpage."""

    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str
    title: str | None = None
    description: str | None = None
    text: str = Field(max_length=MAX_TEXT_CHARS)
    truncated: bool = False


def _validate_public_http_url(url: str) -> None:
    """Reject non-web schemes, local hostnames, and non-public IP destinations."""
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS webpage URLs are supported.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported.")
    if parsed.port not in (None, 80, 443):
        raise ValueError("Custom ports are not supported.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise ValueError("Localhost URLs are not supported.")

    try:
        addresses = {
            ipaddress.ip_address(answer[4][0])
            for answer in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        try:
            addresses = {ipaddress.ip_address(hostname)}
        except ValueError:
            raise ValueError("Could not resolve the webpage hostname.") from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private or non-public network addresses are not supported.")


def _extract_page(url: str, final_url: str, html: str) -> PageContent:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "template", "svg"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = description_tag.get("content", "").strip() if description_tag else None

    main = soup.find("main") or soup.find("article") or soup.body or soup
    full_text = " ".join(main.stripped_strings)
    truncated = len(full_text) > MAX_TEXT_CHARS

    return PageContent(
        url=url,
        final_url=final_url,
        title=title or None,
        description=description or None,
        text=full_text[:MAX_TEXT_CHARS],
        truncated=truncated,
    )


def get_page_url(url: str, *, timeout: float = 15.0) -> PageContent:
    """Fetch a public webpage with HTTPX and return readable, bounded text.

    This function only retrieves and parses page content; it does not execute
    page JavaScript, interact with forms, or follow page-provided instructions.
    Redirect targets are validated before they are fetched.
    """
    current_url = url.strip()
    if not current_url:
        raise ValueError("URL must not be empty.")

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(follow_redirects=False, timeout=timeout, headers=headers) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_public_http_url(current_url)
            with client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Webpage returned a redirect without a location.")
                    current_url = urljoin(str(response.url), location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise ValueError("URL did not return an HTML webpage.")

                chunks: list[bytes] = []
                byte_count = 0
                for chunk in response.iter_bytes():
                    byte_count += len(chunk)
                    if byte_count > MAX_RESPONSE_BYTES:
                        raise ValueError("Webpage response exceeded the 2 MB size limit.")
                    chunks.append(chunk)

                html = b"".join(chunks).decode(
                    response.encoding or "utf-8",
                    errors="replace",
                )
                return _extract_page(url, str(response.url), html)

    raise ValueError(f"Webpage exceeded the {MAX_REDIRECTS}-redirect limit.")
