"""Narrow Ashby-hosted application form adapter.

The employer API is intentionally not used: this adapter works only on the
candidate-facing Ashby hosted form and never submits without an explicit call
from the review workflow.
"""

from __future__ import annotations

import base64
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from recruiter_agent.applications.models import ApplicationField
from recruiter_agent.profile.models import CandidateProfile
from recruiter_agent.tools.read_webpage import _validate_public_http_url

ASHBY_HOST = "jobs.ashbyhq.com"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
CAPTCHA_PATTERN = re.compile(r"captcha|verify (that )?you are human", re.IGNORECASE)
SUCCESS_PATTERN = re.compile(
    r"thank you for applying|application (was )?submitted|successfully applied",
    re.IGNORECASE,
)


class ApplicationBlockedError(ValueError):
    """The page or form cannot be handled safely by this adapter."""


@dataclass(frozen=True)
class FieldLocator:
    """A locator tied to a discovered form field, not model-provided selectors."""

    indexes: tuple[int, ...]
    kind: str
    option_values: tuple[str, ...] = ()


@dataclass
class TrafficPolicy:
    """Block page writes, then all page traffic, until the user confirms this draft."""

    locked: bool = True
    review_locked: bool = False
    submission_authorized: bool = False


def validate_ashby_url(url: str) -> str:
    """Accept only public HTTPS Ashby-hosted job pages."""
    normalized = url.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme.casefold() != "https" or parsed.hostname != ASHBY_HOST:
        raise ApplicationBlockedError("Use a public Ashby-hosted job URL on jobs.ashbyhq.com.")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ApplicationBlockedError("The Ashby job URL has unsupported connection details.")
    _validate_public_http_url(normalized)
    return normalized


def _validate_browser_destination(url: str) -> bool:
    """Allow public Ashby pages and assets while blocking local/private addresses."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.casefold() != "https"
        or port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        return False
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host or not (
        host == "ashbyhq.com"
        or host.endswith(".ashbyhq.com")
        or host == "ashbycdn.com"
        or host.endswith(".ashbycdn.com")
    ):
        return False
    try:
        _validate_public_http_url(url)
    except ValueError:
        return False
    try:
        addresses = {
            ipaddress.ip_address(answer[4][0])
            for answer in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except OSError:
        return False
    return bool(addresses) and all(address.is_global for address in addresses)


def _allows_page_request(method: str, policy: TrafficPolicy) -> bool:
    if policy.submission_authorized:
        return True
    if policy.review_locked:
        return False
    return not policy.locked or method in {"GET", "HEAD", "OPTIONS"}


def _allows_websocket(url: str, policy: TrafficPolicy) -> bool:
    return policy.submission_authorized and _validate_browser_destination(url)


class AshbyFormSession:
    """A short-lived browser session that fills known fields and waits for review."""

    def __init__(
        self,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        page: Page,
        form_index: int,
        fields: list[ApplicationField],
        locators: dict[str, FieldLocator],
        traffic_policy: TrafficPolicy,
    ):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.form_index = form_index
        self.fields = fields
        self.locators = locators
        self.traffic_policy = traffic_policy
        self.submitted = False
        self.pending_files: dict[str, dict[str, object]] = {}

    @classmethod
    async def open(cls, url: str, profile: CandidateProfile) -> AshbyFormSession:
        """Open a public Ashby application form and prefill only known profile facts."""
        safe_url = validate_ashby_url(url)
        playwright = await async_playwright().start()
        browser = None
        context = None
        traffic_policy = TrafficPolicy()
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=False,
                java_script_enabled=True,
                service_workers="block",
            )

            async def validate_request(route) -> None:
                if not _validate_browser_destination(route.request.url):
                    await route.abort()
                    return
                if not _allows_page_request(route.request.method, traffic_policy):
                    await route.abort()
                    return
                await route.continue_()

            async def validate_websocket(websocket) -> None:
                if not _allows_websocket(websocket.url, traffic_policy):
                    await websocket.close(code=1008, reason="User confirmation is required")
                    return
                await websocket.connect_to_server()

            await context.route("**/*", validate_request)
            await context.route_web_socket("**/*", validate_websocket)
            page = await context.new_page()
            response = await page.goto(safe_url, wait_until="domcontentloaded", timeout=20_000)
            if response is None or response.status >= 400:
                raise ApplicationBlockedError("Ashby did not return a usable job page.")
            if urlsplit(page.url).hostname != ASHBY_HOST:
                raise ApplicationBlockedError("Ashby redirected away from its hosted job page.")

            form, form_index = await _find_application_form(page)
            fields, locators = await _read_fields(form)
            traffic_policy.review_locked = True
            session = cls(
                playwright,
                browser,
                context,
                page,
                form_index,
                fields,
                locators,
                traffic_policy,
            )
            values = _profile_values(fields, profile)
            await session.update_values(values, sources={key: "profile" for key in values})
            return session
        except Exception as exc:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            await playwright.stop()
            if isinstance(exc, ApplicationBlockedError):
                raise
            raise ApplicationBlockedError(
                "Could not open or inspect the Ashby form. It may require manual steps."
            ) from None

    async def update_values(
        self,
        values: dict[str, str | bool | None],
        *,
        sources: dict[str, str] | None = None,
    ) -> list[ApplicationField]:
        """Apply only user-confirmable values to the previously discovered controls."""
        form = self.page.locator("form").nth(self.form_index)
        current_fields, current_locators = await _read_fields(form)
        if [field.id for field in current_fields] != [field.id for field in self.fields]:
            raise ApplicationBlockedError("The Ashby form changed. Prepare it again before review.")

        updated = {field.id: field.model_copy(deep=True) for field in self.fields}
        for field_id, value in values.items():
            if field_id not in updated:
                raise ApplicationBlockedError("An application field is no longer available.")
            field = updated[field_id]
            locator = current_locators[field_id]
            control = form.locator("input, textarea, select").nth(locator.indexes[0])
            if field.kind in {"text", "email", "phone", "url", "textarea"}:
                if value is not None and not isinstance(value, str):
                    raise ApplicationBlockedError("Enter text for this application field.")
                await control.fill(value or "")
            elif field.kind == "select":
                if locator.kind == "radio" and value is not None:
                    option_index = next(
                        (
                            index
                            for index, option_value in enumerate(locator.option_values)
                            if option_value == value or updated[field_id].options[index] == value
                        ),
                        None,
                    )
                    if option_index is None:
                        raise ApplicationBlockedError("Choose one of the displayed options.")
                    await (
                        form.locator("input, textarea, select")
                        .nth(locator.indexes[option_index])
                        .check()
                    )
                elif value is not None:
                    await control.select_option(label=str(value))
            elif field.kind == "checkbox":
                if not isinstance(value, bool):
                    raise ApplicationBlockedError("Choose whether to check this box.")
                await control.set_checked(value)
            elif field.kind == "file":
                raise ApplicationBlockedError("Choose a resume file using the file upload control.")
            field.value = value
            field.source = (sources or {}).get(field_id, "user")
        self.fields = [updated[field.id] for field in self.fields]
        return self.fields

    async def attach_file(
        self,
        field_id: str,
        name: str,
        content_type: str,
        encoded_content: str,
    ) -> list[ApplicationField]:
        """Attach a user-selected resume kept in memory by the browser session."""
        locator = self.locators.get(field_id)
        if locator is None or locator.kind != "file":
            raise ApplicationBlockedError("This form does not contain that file field.")
        if content_type not in ALLOWED_FILE_TYPES:
            raise ApplicationBlockedError("Choose a PDF, DOC, or DOCX file.")
        try:
            content = base64.b64decode(encoded_content, validate=True)
        except ValueError as exc:
            raise ApplicationBlockedError("The selected file could not be read.") from exc
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ApplicationBlockedError("The resume must be smaller than 10 MB.")
        self.pending_files[field_id] = {
            "name": name,
            "mimeType": content_type,
            "buffer": content,
        }
        for field in self.fields:
            if field.id == field_id:
                field.value = name
                field.file_name = name
                field.source = "user"
        return self.fields

    async def submit_once(self) -> str:
        """Submit exactly once, after the caller validates the reviewed snapshot."""
        if self.submitted:
            raise ApplicationBlockedError("This application has already been submitted.")
        form = self.page.locator("form").nth(self.form_index)
        self.traffic_policy.submission_authorized = True
        for field_id, file_payload in self.pending_files.items():
            locator = self.locators[field_id]
            control = form.locator("input, textarea, select").nth(locator.indexes[0])
            await control.set_input_files(file_payload)
        self.pending_files.clear()
        _, buttons = await self._valid_submit_controls()
        self.submitted = True
        await buttons.click(timeout=5000)
        await self.page.wait_for_timeout(1200)
        if CAPTCHA_PATTERN.search(await self.page.locator("body").inner_text()):
            return "uncertain"
        if SUCCESS_PATTERN.search(await self.page.locator("body").inner_text()):
            return "submitted"
        return "uncertain"

    async def validate_before_submit(self) -> None:
        """Check native browser constraints before consuming the confirmation token."""
        form = self.page.locator("form").nth(self.form_index)
        valid = await form.evaluate(
            """form => Array.from(form.elements).every(element =>
              typeof element.checkValidity !== 'function' || element.type === 'file' ||
              element.checkValidity())"""
        )
        if not valid:
            raise ApplicationBlockedError("Ashby reports unanswered or invalid required fields.")
        buttons = form.locator('button[type="submit"], button:not([type]), input[type="submit"]')
        if await buttons.count() != 1:
            raise ApplicationBlockedError("Could not identify one safe Ashby submit button.")

    async def matches_review(self, reviewed_fields: list[ApplicationField]) -> bool:
        """Ensure the live form still contains exactly the values the user reviewed."""
        form = self.page.locator("form").nth(self.form_index)
        current_fields, _ = await _read_fields(form)
        if [field.id for field in current_fields] != [field.id for field in reviewed_fields]:
            self.fields = current_fields
            return False
        for current, reviewed in zip(current_fields, reviewed_fields, strict=True):
            if current.kind == "file":
                pending = self.pending_files.get(current.id)
                if reviewed.file_name and pending and pending["name"] == reviewed.file_name:
                    continue
                if current.file_name != reviewed.file_name:
                    current.source = "user" if current.file_name else "unanswered"
            elif current.value != reviewed.value:
                current.source = "user" if current.value not in (None, "", False) else "unanswered"
            if current.value != reviewed.value or current.file_name != reviewed.file_name:
                self.fields = current_fields
                return False
        return True

    async def _valid_submit_controls(self):
        form = self.page.locator("form").nth(self.form_index)
        if not await form.evaluate("element => element.checkValidity()"):
            raise ApplicationBlockedError("Ashby reports unanswered or invalid required fields.")
        buttons = form.locator('button[type="submit"], button:not([type]), input[type="submit"]')
        if await buttons.count() != 1:
            raise ApplicationBlockedError("Could not identify one safe Ashby submit button.")
        return form, buttons

    async def close(self) -> None:
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()


async def _find_application_form(page: Page):
    """Find one plausible applicant form, clicking one unambiguous Apply action if needed."""
    forms = page.locator("form")
    matches = await _application_form_indexes(forms)
    if not matches:
        buttons = page.get_by_role("button", name=re.compile(r"^apply( for this job)?$", re.I))
        links = page.get_by_role("link", name=re.compile(r"^apply( for this job)?$", re.I))
        button_count = await buttons.count()
        link_count = await links.count()
        if button_count + link_count != 1:
            raise ApplicationBlockedError("Could not identify one Ashby application form.")
        if button_count:
            await buttons.click(timeout=5000)
        else:
            await links.click(timeout=5000)
        await page.wait_for_timeout(250)
        forms = page.locator("form")
        matches = await _application_form_indexes(forms)
    if len(matches) != 1:
        raise ApplicationBlockedError("Could not identify one unambiguous Ashby application form.")
    form = forms.nth(matches[0])
    if CAPTCHA_PATTERN.search(await page.locator("body").inner_text()):
        raise ApplicationBlockedError("Ashby requires a human CAPTCHA; continue manually.")
    return form, matches[0]


async def _application_form_indexes(forms) -> list[int]:
    """Require applicant-like fields so a newsletter or unrelated form is never selected."""
    matches = []
    for index in range(await forms.count()):
        form = forms.nth(index)
        try:
            fields, _ = await _read_fields(form)
        except ApplicationBlockedError:
            continue
        labels = {" ".join(field.label.casefold().split()) for field in fields}
        has_contact = bool(
            labels
            & {
                "name",
                "full name",
                "first name",
                "last name",
                "email",
                "email address",
                "phone",
                "phone number",
            }
        )
        has_resume = any(
            field.kind == "file"
            and re.search(r"resume|cv|curriculum vitae", field.label, re.IGNORECASE)
            for field in fields
        )
        if has_resume or (has_contact and len(fields) >= 2):
            matches.append(index)
    return matches


async def _read_fields(form) -> tuple[list[ApplicationField], dict[str, FieldLocator]]:
    """Read visible native form controls; hidden fields and page instructions are ignored."""
    raw = await form.locator("input, textarea, select").evaluate_all(
        """elements => elements.map((el, index) => {
          const labels = Array.from(el.labels || []).map(label => label.innerText.trim());
          const fieldset = el.closest('fieldset');
          const legend = fieldset?.querySelector('legend')?.innerText?.trim() || '';
          const optionValues = el.tagName === 'SELECT'
            ? Array.from(el.options).filter(option => option.value).map(option => ({
                label: option.label.trim(), value: option.value
              })) : [];
          return {
            index, tag: el.tagName.toLowerCase(), type: (el.type || '').toLowerCase(),
            name: el.name || '', legend, label: labels.filter(Boolean).join(' ') ||
              el.getAttribute('aria-label') || legend || el.placeholder || el.name || '',
            required: Boolean(el.required) || el.getAttribute('aria-required') === 'true',
            visible: Boolean(el.getClientRects().length), value: el.value || '',
            checked: Boolean(el.checked), options: optionValues,
            selectedLabel: el.tagName === 'SELECT' ? el.selectedOptions[0]?.label || '' : '',
            multiple: el.tagName === 'SELECT' && el.multiple,
            fileName: el.type === 'file' ? el.files?.[0]?.name || '' : ''
          };
        })"""
    )
    fields: list[ApplicationField] = []
    locators: dict[str, FieldLocator] = {}
    radio_groups: dict[str, list[dict]] = {}
    for item in raw:
        if not item["visible"] or item["type"] in {"hidden", "submit", "button", "reset", "image"}:
            continue
        if item["multiple"]:
            raise ApplicationBlockedError(
                "Ashby uses a multi-select field this adapter cannot review safely."
            )
        if item["type"] in {"radio"}:
            radio_groups.setdefault(item["name"] or f"radio-{item['index']}", []).append(item)
            continue
        if (
            item["type"]
            not in {"file", "checkbox", "email", "tel", "url", "text", "", "number", "date"}
            and item["tag"] != "textarea"
            and item["tag"] != "select"
        ):
            raise ApplicationBlockedError(
                "Ashby uses a form control this adapter cannot review safely."
            )
        field = _field_from_dom(item)
        if field is None:
            continue
        fields.append(field)
        option_values = tuple(option["value"] for option in item["options"])
        locators[field.id] = FieldLocator((item["index"],), field.kind, option_values)

    for name, group in radio_groups.items():
        first = group[0]
        options = [item["label"] or item["value"] for item in group]
        selected = next((item["label"] or item["value"] for item in group if item["checked"]), None)
        field_id = f"field-{first['index']}"
        fields.append(
            ApplicationField(
                id=field_id,
                label=first["legend"] or name,
                kind="select",
                required=any(item["required"] for item in group),
                value=selected,
                options=options,
                source="unanswered" if selected is None else "user",
            )
        )
        locators[field_id] = FieldLocator(
            tuple(item["index"] for item in group),
            "radio",
            tuple(item["value"] for item in group),
        )
    fields.sort(key=lambda field: int(field.id.removeprefix("field-")))
    if not fields:
        raise ApplicationBlockedError("The Ashby form has no supported visible fields.")
    return fields, locators


def _field_from_dom(item: dict) -> ApplicationField | None:
    input_type = item["type"]
    if input_type == "file":
        kind = "file"
    elif item["tag"] == "textarea":
        kind = "textarea"
    elif item["tag"] == "select":
        kind = "select"
    elif input_type == "checkbox":
        kind = "checkbox"
    elif input_type == "email":
        kind = "email"
    elif input_type == "tel":
        kind = "phone"
    elif input_type == "url":
        kind = "url"
    elif input_type in {"text", "", "number", "date"}:
        kind = "text"
    else:
        return None
    if kind == "file":
        value = item["fileName"] or None
    elif kind == "checkbox":
        value = item["checked"]
    elif kind == "select":
        value = item["selectedLabel"] or None
    else:
        value = item["value"] or None
    options = [option["label"] for option in item["options"]]
    return ApplicationField(
        id=f"field-{item['index']}",
        label=item["label"] or f"Unlabeled form field {item['index'] + 1}",
        kind=kind,
        required=item["required"],
        value=value,
        options=options,
        source="unanswered" if value in (None, "", False) else "user",
        file_name=item["fileName"] or None,
    )


def _profile_values(fields: list[ApplicationField], profile: CandidateProfile) -> dict[str, str]:
    """Map only unambiguous profile contact fields; never infer custom answers."""
    contact = profile.contact
    full_name = (contact.full_name or "").strip()
    first_name, _, last_name = full_name.partition(" ")
    known = {
        "name": full_name,
        "full name": full_name,
        "first name": first_name,
        "last name": last_name,
        "email": contact.email or "",
        "email address": contact.email or "",
        "phone": contact.phone or "",
        "phone number": contact.phone or "",
        "linkedin": contact.linkedin_url or "",
        "linkedin url": contact.linkedin_url or "",
    }
    mapped = {}
    for field in fields:
        label = re.sub(r"[^a-z0-9 ]", " ", field.label.casefold())
        label = " ".join(label.split())
        value = known.get(label)
        if value and field.kind in {"text", "email", "phone", "url"} and not field.value:
            mapped[field.id] = value
    return mapped
