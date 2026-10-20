"""Read-only rendered webpage retrieval using Playwright."""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT_CHARS = 30_000
NAVIGATION_TIMEOUT_MS = 20_000
USER_AGENT = "recruiter-agent/0.1 (read-only job research)"
logger = logging.getLogger(__name__)


class PageContent(BaseModel):
    """Bounded, plain-text content and metadata extracted from a rendered page."""

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
            for answer in socket.getaddrinfo(
                hostname,
                parsed.port or 443,
                type=socket.SOCK_STREAM,
            )
        }
    except OSError as exc:
        try:
            addresses = {ipaddress.ip_address(hostname)}
        except ValueError:
            raise ValueError("Could not resolve the webpage hostname.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private or non-public network addresses are not supported.")


async def _read_page(url: str, timeout: float) -> PageContent:
    _validate_public_http_url(url)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            channel="chrome",
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            accept_downloads=False,
            java_script_enabled=True,
        )

        async def validate_navigation(route) -> None:
            try:
                _validate_public_http_url(route.request.url)
            except ValueError:
                await route.abort()
                return
            await route.continue_()

        await context.route("**/*", validate_navigation)
        page = await context.new_page()
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=min(int(timeout * 1000), NAVIGATION_TIMEOUT_MS),
            )
            if response is None:
                raise ValueError("The webpage did not return a document response.")
            if response.status >= 400:
                raise ValueError(f"Webpage returned HTTP {response.status}.")
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                # Some sites poll continuously; DOM content is still sufficient.
                pass
            title = await page.title()
            try:
                description = await page.locator('meta[name="description"]').get_attribute(
                    "content",
                    timeout=1500,
                )
            except PlaywrightTimeoutError:
                description = None
            text = await page.locator("body").inner_text(timeout=3000)
            normalized_text = " ".join(text.split())
            return PageContent(
                url=url,
                final_url=page.url,
                title=title.strip() or None,
                description=description.strip() if description and description.strip() else None,
                text=normalized_text[:MAX_TEXT_CHARS],
                truncated=len(normalized_text) > MAX_TEXT_CHARS,
            )
        finally:
            await context.close()
            await browser.close()


def get_page_url(url: str, *, timeout: float = 15.0) -> PageContent:
    """Render a public page and extract visible text; never interact with forms."""
    normalized_url = url.strip()
    if not normalized_url:
        raise ValueError("URL must not be empty.")
    host = urlsplit(normalized_url).hostname or "invalid"
    logger.info("webpage_fetch_started", extra={"event": "webpage_fetch_started", "host": host})
    page_content = asyncio.run(_read_page(normalized_url, timeout))
    logger.info(
        "webpage_fetch_completed",
        extra={
            "event": "webpage_fetch_completed",
            "host": urlsplit(page_content.final_url).hostname or "invalid",
            "text_length": len(page_content.text),
            "truncated": page_content.truncated,
        },
    )
    return page_content
