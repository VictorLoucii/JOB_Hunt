"""
Tests for server.config — UserProfile loading and validation of config.yaml.

Uses config.example.yaml and tmp_path files; never the real config.yaml.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.config import PROJECT_ROOT, UserProfile


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_config_loads_and_validates():
    profile = UserProfile(PROJECT_ROOT / "config.example.yaml")
    profile.validate()
    assert profile.name == "Your Name"
    assert profile.graduation == "2026"
    assert "Python" in profile.skills
    assert profile.llm_fallback_models == ["google/gemini-2.5-flash"]
    assert profile.llm_temperature == 0.7
    assert profile.llm_max_tokens == 1024
    assert profile.constraints.max_experience_required_years == 1
    assert profile.constraints.allowed_locations == ["Location 1", "Location 2", "Remote"]


def test_missing_file_uses_defaults(tmp_path):
    profile = UserProfile(tmp_path / "absent.yaml")
    assert profile.name == ""
    assert profile.skills == []
    assert profile.tone == "professional"
    assert profile.llm_model == "deepseek/deepseek-chat"
    assert profile.prompt_version == "email_draft.txt"
    assert profile.resume_dir is None


def test_unquoted_number_becomes_text(tmp_path):
    path = _write_config(tmp_path, "user:\n  graduation: 2026\n")
    assert UserProfile(path).graduation == "2026"


def test_empty_values_use_defaults(tmp_path):
    path = _write_config(tmp_path, "user:\n  tone:\nllm:\n")
    profile = UserProfile(path)
    assert profile.tone == "professional"
    assert profile.llm_model == "deepseek/deepseek-chat"


def test_unknown_sections_are_ignored(tmp_path):
    path = _write_config(tmp_path, "targets:\n  type: paid\nuser:\n  name: Ada\n")
    assert UserProfile(path).name == "Ada"


def test_wrong_type_fails_at_load(tmp_path):
    path = _write_config(tmp_path, "llm:\n  temperature: hot\n")
    with pytest.raises(ValueError, match=r"(?s)Invalid config\.yaml.*llm\.temperature"):
        UserProfile(path)


def test_resume_dir_expands_home(tmp_path):
    path = _write_config(tmp_path, "resume:\n  dir: ~/Resumes\n")
    assert UserProfile(path).resume_dir == Path("~/Resumes").expanduser()


def test_error_leaves_out_config_values(tmp_path, caplog):
    path = _write_config(tmp_path, "llm:\n  temperature: my-private-value\n")
    with pytest.raises(ValueError) as exc_info:
        UserProfile(path)
    assert "llm.temperature" in str(exc_info.value)
    assert "my-private-value" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert "my-private-value" not in caplog.text
