import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from recruiter_agent.profile.loader import load_profile
from recruiter_agent.profile.models import CandidateProfile, Preferences


def test_preferences_default_to_unknown_or_empty() -> None:
    preferences = Preferences()

    assert preferences.target_titles == []
    assert preferences.remote_preference is None
    assert preferences.compensation_minimum is None


def test_profile_loader_validates_profile_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "preferences": {"target_titles": ["Applied AI Engineer"]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RECRUITER_AGENT_PROFILE_PATH", str(profile_path))

    profile = load_profile()

    assert isinstance(profile, CandidateProfile)
    assert profile.preferences.target_titles == ["Applied AI Engineer"]


def test_profile_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"schema_version": 1, "prefereces": {}})


def test_profile_missing_file_has_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_profile = tmp_path / "missing.json"
    monkeypatch.setenv("RECRUITER_AGENT_PROFILE_PATH", str(missing_profile))

    with pytest.raises(FileNotFoundError, match="Create data/profile.json"):
        load_profile()
