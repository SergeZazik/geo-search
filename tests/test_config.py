import pytest

from app.config import Settings


def test_empty_variables_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # docker compose passes OPENAI_API_KEY= and OPENAI_MODEL= when they are not set.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key is None
    assert settings.openai_model == Settings.model_fields["openai_model"].default
