import json
import pytest
from usage_client import read_token, NoCredentialsError


def _write_creds(tmp_path, obj):
    p = tmp_path / ".credentials.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_read_token_returns_access_token(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok-123"}})
    assert read_token(path) == "tok-123"


def test_read_token_missing_file_raises(tmp_path):
    with pytest.raises(NoCredentialsError):
        read_token(str(tmp_path / "yok.json"))


def test_read_token_missing_field_raises(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {}})
    with pytest.raises(NoCredentialsError):
        read_token(path)
