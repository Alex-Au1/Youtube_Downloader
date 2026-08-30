# Youtube_Downloader

A GUI YouTube downloader split into two processes that talk over HTTP:

- **`frontend/`** — a Tkinter desktop app. Searches, shows results, asks download questions, streams progress, writes the finished file to disk.
- **`backend/`** — a Django app on port **9001**. Wraps `yt-dlp`, does the actual downloading, serves the file back.

The frontend never calls `yt-dlp` itself. Every piece of YouTube data comes from the backend over HTTP.

## Read these before working

Detailed notes live in `AI Agent Help/`. Read the ones relevant to your task — they exist so you don't have to re-derive this:

| Doc | Read it when |
| --- | --- |
| [Architecture](AI%20Agent%20Help/architecture/CLAUDE.md) | Touching anything that crosses the frontend/backend boundary. **Contains the download-options wire format, which is easy to break silently.** |
| [Backend](AI%20Agent%20Help/backend/CLAUDE.md) | Changing Django views, the download pipeline, format codes, or progress reporting. |
| [Frontend](AI%20Agent%20Help/frontend/CLAUDE.md) | Changing the Tkinter app. **Contains the threading contract — the single easiest thing to break here.** |
| [Environment](AI%20Agent%20Help/environment/CLAUDE.md) | Running either half, debugging `yt-dlp`/PO-token failures, or anything dependency related. |
| [Conventions](AI%20Agent%20Help/conventions/CLAUDE.md) | Writing any code, and especially before testing a change. |

## Running it

Both halves, from their own directories. The backend must be up first.

```powershell
# backend
cd backend
py -3 manage.py runserver 9001

# frontend
cd frontend
py -3 exe_main.py
```

## Four things that will trip you up

**1. `backend/venv/` is dead. Do not use it.** It holds `yt-dlp 2025.2.19` and `bgutil-ytdlp-pot-provider 0.7.3`, both long stale. `py -3` resolves to the global `C:\Users\AlexX\AppData\Local\Programs\Python\Python313`, which has the real, current dependencies. The venv is never activated by either run command. If you need to check an installed version, check the global interpreter.

**2. `ALLOWED_HOSTS` does not include `127.0.0.1`.** It is `['localhost', '192.168.1.72', '192.168.2.86']` ([backend/src/settings.py](backend/src/settings.py)). Hitting the backend at `http://127.0.0.1:9001` returns **HTTP 400 DisallowedHost**, which looks like an app bug and isn't. Use `http://localhost:9001`.

**3. Downloads need a separate PO token provider running.** The backend points `yt-dlp` at a bgutil provider on `http://127.0.0.1:9002` (`Extractor_Args`, [backend/yt_downloader/models.py](backend/yt_downloader/models.py)). That's a different project, hosted under IIS. If metadata fetches fail with extractor errors, check the provider before suspecting this repo. See [Environment](AI%20Agent%20Help/environment/CLAUDE.md).

**4. Importing the frontend module builds the whole GUI.** `youtube_downloader.py` ends with a module-level `if (__name__ != "__main__"):` block that creates the `Tk()` root, the `Application`, the menu bar and the worker threads *at import time*. `run_main()` only calls `mainloop()`. So `import youtube_va_downloader.youtube_downloader` has real side effects — which is also what makes headless testing possible. See [Conventions](AI%20Agent%20Help/conventions/CLAUDE.md).

## Layout

```
backend/
  manage.py
  src/                     Django project (settings, urls, wsgi/asgi)
  yt_downloader/
    views.py               the 7 HTTP endpoints
    models.py              yt-dlp wrapper + format tables. NO Django ORM models.
    urls.py
    secrets.py             gitignored; defines Download_Folder
    tools/format_display.py
frontend/
  exe_main.py              entry point
  setup.txt                gitignored; 3 lines of user settings incl. backend URL
  ffmpeg.exe, ffprobe.exe  required for post-processing
  youtube_va_downloader/
    youtube_downloader.py  the entire Tkinter UI (~1600 lines)
    download_requests.py   HTTP client for the backend
    download_video.py      format enums/tables + file move & tagging
    format_display.py      formatting helpers + thumbnail fetching
    search_video.py        legacy; superseded by the backend search endpoint
    set_up.py              setup.txt reader/writer
AI Agent Help/             these docs
```

## Repo

`https://github.com/Alex-Au1/Youtube_Downloader`, default branch `main`.

Gitignored and therefore absent on a fresh clone: `secrets.py`, `setup.txt`, `dist`, `build`, `__pycache__`, `ff*.exe`, `backend/downloads`.
