# Architecture — how the two halves talk

Back to [root CLAUDE.md](../../CLAUDE.md).

The frontend is a pure HTTP client of the backend. All calls go through `DownloadRequests` in [frontend/youtube_va_downloader/download_requests.py](../../frontend/youtube_va_downloader/download_requests.py); nothing else in the frontend should make HTTP calls to the backend.

The base URL is **not** a constant. It is line 3 of `frontend/setup.txt`, read at startup by `run_main()` and pushed in via `DownloadRequests.changeHostUrl()`.

> **Landmine:** `Host_Url` in `download_requests.py` is only ever assigned inside `changeHostUrl()` via `global`. It has no module-level definition. Any code path that calls a `DownloadRequests` method before `changeHostUrl()` runs dies with `NameError`. If you add a new entry point, make sure it goes through `run_main()`.

## Endpoints

Registered in [backend/yt_downloader/urls.py](../../backend/yt_downloader/urls.py), all at the root.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/get_youtube_search/` | `search_query`, `no_of_searches` → search results |
| GET | `/get_metadata/` | `link`, optional `opts` → raw `yt-dlp` info dict |
| POST | `/prepare_download/` | JSON `{video, options, folder}` → starts the download, returns `download_id` |
| GET | `/download_stream/` | `download_id` → **SSE** progress stream |
| GET | `/get_progress/` | `download_id` → single progress string (polling alternative to the stream) |
| GET | `/get_download/` | `download_id` → the finished file as an attachment |
| GET | `/clean_download/` | `download_id` → deletes the server-side temp folder |

## The download-options wire format

**This is the most fragile contract in the repo.** Read this before touching either the download questions or `prepare_download`.

The frontend sends `options` as a **flat list of the answer strings the user picked**, in the order they were asked. `prepare_download` ([backend/yt_downloader/models.py](../../backend/yt_downloader/models.py)) then reads that list **positionally** and compares the strings **exactly**.

Three shapes exist:

| User path | `options` |
| --- | --- |
| Audio | `["Audio", quality, audio_format]` |
| Video with audio | `["Video", quality, "Yes! Download video with audio.", audio_quality, video_format]` |
| Video without audio | `["Video", quality, "No! Download video without audio.", video_format]` |

Where `quality` is `"best quality"` or `"worst quality"`, and a format may be the literal `"don't care"`.

Consequences you must respect:

- **The answer labels are protocol, not UI copy.** Renaming `"Yes! Download video with audio."` in the UI silently changes which branch the backend takes. In the frontend these are hoisted into the constants `AUDIO_ONLY`, `VIDEO`, `WITH_AUDIO`, `WITHOUT_AUDIO`, `QUALITY_OPTIONS`. Change a label and you must change `prepare_download` in lockstep.
- **Inserting a question shifts every index after it.** `prepare_download` reads `options[0]`..`options[4]` by hand, including a `try: options[4] except: options[3]` to cope with the two video shapes.
- There is no validation on either side. A mismatch produces a wrong download, not an error.

The questions themselves are declared once, as data, in `DOWNLOAD_STEPS` in [frontend/youtube_va_downloader/youtube_downloader.py](../../frontend/youtube_va_downloader/youtube_downloader.py). Each step carries a `when` predicate over the answers so far, and those predicates index the list at the same positions the backend does — so the spec and `prepare_download` line up and can be diffed against each other by eye. See [Frontend](../frontend/CLAUDE.md).

### Adding new options: use a new field, not a new position

The remix feature is the worked example. It is asked *after* the questions and *before* the folder chooser, but it is deliberately **not** a `DownloadStep` and never enters `options`. It travels as its own key in the POST body:

```json
{"video": {...}, "options": [...], "folder": "...", "remix": {"half_steps": 2, "speed": 1.25}}
```

`remix` is `null` or absent when not wanted, and the backend reads it with `.get()`, so an older client still works. Prefer this pattern for anything new — appending to `options` shifts every index after it and silently changes which branch `prepare_download` takes.

## Download lifecycle

1. `POST /prepare_download/` — backend creates a `YoutubeDownload` with a `uuid4().hex` id, registers it in the module-level `Downloads` dict in `views.py`, and **starts a background thread** that runs `yt-dlp`. It returns immediately with `download_id` and the resolved video info.
2. `GET /download_stream/` — SSE. Emits one event per second:
   - `{"type": "progress", "data": "<human-readable string>"}`
   - `{"type": "done"}` once finished, then closes.
   - `{"type": "error", "data": "<reason>"}` if the download died, then closes.

   The frontend consumes this with `sseclient` and stores the latest string in the module global `Last_Progress`, which the loading screen renders. It **raises** on `error`, so the reason reaches the error dialog. Without that event the stream would never end, because it otherwise only exits when `Finished_Download` gets a value — which a dead worker thread never sets.

   **The stream ending is not the same as the download finishing.** It also ends when the
   connection is closed, which long downloads invite: IIS terminates a FastCGI request at
   `requestTimeout`, 90 seconds by default, and neither `web.config` here raises it. The
   client therefore treats a stream that stopped without saying `done` as a dropped
   connection and reconnects, up to `STREAM_RECONNECT_LIMIT` times; only `done` or `error`
   ends the wait. Reading the stream in a plain `for` loop and continuing afterwards is
   the bug that produced `KeyError: 'content-disposition'` on large files -- the file was
   requested before it existed, and `get_download` answers with json in that case.
3. `GET /get_download/` — returns the file, streamed to disk in chunks so a large download never has to fit in memory. **Check `content-disposition` is present**: when the file is not ready this returns json, not a file. **This is one-shot:** it `pop`s the entry from `Finished_Download`, so a second call returns `{"download_available": False}`.
4. Frontend writes the bytes to the CWD, then `DLUtils.move_video` relocates it to the user's chosen folder and applies tags.
5. `GET /clean_download/` — deletes the server-side temp folder and drops the id from `Downloads`.

The folder the user picks is a **frontend** concept. The backend downloads into its own temp folder under `Download_Folder` and never writes to the user's directory.

## Server-side state is in-process globals

`Downloads` (views.py) and `Download_Progress`, `File_Download_Type`, `Download_No`, `Finished_Download`, `Sending_Download` (models.py) are all plain module-level dicts.

This means:

- **Single process only.** Multiple workers, or `runserver`'s autoreloader restarting mid-download, will lose downloads and produce `Download Id Not Registered`. Use `--noreload` when scripting against it.
- Nothing survives a restart. There is no persistence, and none is expected.
- `db.sqlite3` exists but the app does not use it. `models.py` contains **no Django ORM models**, and `yt_downloader` is not even in `INSTALLED_APPS` — it is wired in purely through `urls.py`.
