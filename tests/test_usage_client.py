import json
import pytest
from datetime import datetime, timezone
from usage_client import read_token, NoCredentialsError, parse_usage, UsageData, Window


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


SAMPLE = {
    "five_hour": {"utilization": 30.0, "resets_at": "2026-07-23T21:09:59.349625+00:00"},
    "seven_day": {"utilization": 71.0, "resets_at": "2026-07-25T10:00:00.349653+00:00"},
}


def test_parse_usage_reads_both_windows():
    now = datetime(2026, 7, 23, 21, 0, tzinfo=timezone.utc)
    data = parse_usage(SAMPLE, now)
    assert isinstance(data, UsageData)
    assert data.five_hour.utilization == 30.0
    assert data.five_hour.resets_at == datetime(2026, 7, 23, 21, 9, 59, 349625, tzinfo=timezone.utc)
    assert data.seven_day.utilization == 71.0
    assert data.fetched_at == now


def test_parse_usage_missing_window_is_none():
    data = parse_usage({"five_hour": None, "seven_day": SAMPLE["seven_day"]}, datetime.now(timezone.utc))
    assert data.five_hour is None
    assert data.seven_day.utilization == 71.0


def test_parse_usage_incomplete_window_is_none():
    data = parse_usage({"five_hour": {"utilization": 5.0}, "seven_day": {}}, datetime.now(timezone.utc))
    assert data.five_hour is None
    assert data.seven_day is None
