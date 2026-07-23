from __future__ import annotations

import json
import os

CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class NoCredentialsError(Exception):
    pass


def read_token(path: str = CREDENTIALS_PATH) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise NoCredentialsError(str(e))
    try:
        return data["claudeAiOauth"]["accessToken"]
    except (KeyError, TypeError):
        raise NoCredentialsError("accessToken bulunamadı")
