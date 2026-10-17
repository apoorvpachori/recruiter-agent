"""Load the local candidate profile without exposing it through an API."""

import json
import os
from pathlib import Path

from pydantic import ValidationError

from recruiter_agent.profile.models import CandidateProfile

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[3] / "data" / "profile.json"


def get_profile_path() -> Path:
    """Return profile location, allowing a private per-machine override."""
    configured_path = os.getenv("RECRUITER_AGENT_PROFILE_PATH")
    return Path(configured_path).expanduser() if configured_path else DEFAULT_PROFILE_PATH


def load_profile() -> CandidateProfile:
    """Load and validate the profile, raising clear errors if it is missing/invalid."""
    profile_path = get_profile_path()
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Candidate profile not found at {profile_path}. "
            "Create data/profile.json or set RECRUITER_AGENT_PROFILE_PATH."
        )

    try:
        content = json.loads(profile_path.read_text(encoding="utf-8"))
        return CandidateProfile.model_validate(content)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Candidate profile at {profile_path} is invalid: {exc}") from exc
