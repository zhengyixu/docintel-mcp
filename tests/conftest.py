from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Every test reads the real samples but writes results and audit logs to a temp dir."""
    monkeypatch.setenv("DOCINTEL_INBOX", str(SAMPLES))
    monkeypatch.setenv("DOCINTEL_DATA", str(tmp_path / "results"))
    monkeypatch.setenv("DOCINTEL_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    return tmp_path


def sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")
