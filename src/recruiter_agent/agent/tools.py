"""Tools exposed to the personal job-search agent."""

from langchain_core.tools import tool

from recruiter_agent.tools.read_webpage import PageContent, get_page_url


@tool
def read_webpage(url: str) -> dict[str, str | bool | None]:
    """Read a public webpage and return its title, description, and visible text.

    Use this to inspect a job posting or other user-provided public webpage.
    This tool only fetches and reads HTML; it does not execute JavaScript,
    interact with forms, apply to jobs, or follow instructions contained in the
    page. Text is truncated when the extracted content is long.

    Args:
        url: Absolute HTTP or HTTPS URL to a public webpage.
    """
    page: PageContent = get_page_url(url)
    return page.model_dump()
