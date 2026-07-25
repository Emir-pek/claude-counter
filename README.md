# Claude Counter

A small always-on-top desktop widget for Windows that shows how much of your
Claude subscription you have used: the 5-hour window and the weekly window,
each with a colored bar, a live countdown, and the local clock time when it
resets.

*Türkçe: [README.tr.md](README.tr.md)*

![Claude Counter](docs/screenshot.png)

> **Note:** the widget's interface is currently in Turkish
> (`5 saatlik` = 5-hour, `Haftalık` = weekly, `güncellendi` = updated).

## Requirements

- Windows
- [Python 3.10+](https://www.python.org/downloads/) (tested on 3.11.9) — during
  setup, tick **"Add python.exe to PATH"**
- [Claude Code](https://claude.com/claude-code) installed and logged in — the
  widget reads its session

## Install and run

1. Download the code: **Code → Download ZIP**, then extract it (or
   `git clone` the repository).
2. Double-click **`baslat.bat`** (Turkish for "start").
3. The first run creates a local `.venv` and installs customtkinter. It takes a
   few seconds and happens only once — later runs open instantly.

The widget refreshes every 60 seconds; the **↻** button refreshes it manually.
Close it with the **✕** button.

To start it automatically with Windows, press `Win+R`, run `shell:startup`, and
put a shortcut to `baslat.bat` in the folder that opens.

## What it does with your data

This program reads your Claude session token, so you should know exactly what
it does before you run it:

- It reads the token from `claudeAiOauth.accessToken` in
  `~/.claude/.credentials.json` **fresh on every request**. It never copies,
  stores, or logs it.
- The only network call it makes is
  `GET https://api.anthropic.com/api/oauth/usage`. It connects to no other
  server and sends no telemetry. See [`usage_client.py`](usage_client.py) — it
  is under 100 lines.
- **That endpoint is undocumented.** It is a private endpoint that Claude Code
  uses for itself. Anthropic may change or remove it without notice, and the
  widget would then stop showing data.
- **It is not the paid API.** The request runs no model and consumes no tokens,
  so it costs nothing and does not appear on any bill. It does not consume your
  5-hour or weekly limit either — it only reports it.
- It polls once every 60 seconds. If you restart it many times in a row, the
  endpoint may answer with HTTP 429; the rows then keep showing the last good
  data.

## Development

```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Run from source without the launcher: `pythonw main.py`

Layout: `main.py` is the refresh loop, `app.py` the CustomTkinter window,
`usage_client.py` the fetch and parse layer, `formatting.py` the countdown and
color rules.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "Python was not found" | Install Python 3.10+ and tick "Add python.exe to PATH" |
| Widget says `Claude oturumu bulunamadı` | Log in with Claude Code first |
| Widget says `Oturum süresi dolmuş` | Your session expired — log in with Claude Code again |
| Widget says `Bağlantı yok` | No internet connection |
| Something broke after an update | Delete the `.venv` folder, then double-click `baslat.bat` again |

## License

MIT — see [LICENSE](LICENSE).
