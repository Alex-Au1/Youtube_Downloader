# Environment — runtime, dependencies, PO tokens

Back to [root CLAUDE.md](../../CLAUDE.md).

## The interpreter

Everything runs on the **global** Python 3.13 at:

```
C:\Users\AlexX\AppData\Local\Programs\Python\Python313\python.exe
```

`py -3` resolves to it. Both documented run commands use `py -3`.

**`backend/venv/` is vestigial.** It is never activated and holds badly stale packages (`yt-dlp 2025.2.19`, `bgutil-ytdlp-pot-provider 0.7.3`). `backend/requirements.txt` describes that dead venv, not the live environment — **do not treat it as the source of truth for versions.** To check what is actually installed:

```powershell
py -3 -m pip list
```

## PO token provider (the usual cause of download failures)

YouTube requires a proof-of-origin token. `yt-dlp` gets one from a **separate service** that is not part of this repo:

- Project: `bgutil-ytdlp-pot-provider`, checked out at `C:\inetpub\wwwroot\bgutil-ytdlp-pot-provider` and hosted under IIS.
- This backend expects to reach it at **`http://127.0.0.1:9002`**, set in `Extractor_Args` in [backend/yt_downloader/models.py](../../backend/yt_downloader/models.py). Note the provider's own upstream default is 4416, so this is a deliberate local override — if you change one, change the other.
- The matching `bgutil-ytdlp-pot-provider` pip plugin must also be installed in the global Python.

**Keep the plugin and the server on the same version.** The plugin warns on any mismatch and hard-refuses on a *major* mismatch. Both sides are currently on 1.3.2.

Confirm the provider chain is healthy:

```powershell
py -3 -m yt_dlp -v --simulate "https://www.youtube.com/watch?v=<id>"
```

Look for `bgutil:http-<version> (external)` in the `PO Token Providers` debug line. If it says `unavailable`, the provider isn't reachable and downloads will fail regardless of anything in this repo.

There is also an orphaned `yt-dlp-get-pot 0.3.0` in the global environment — the deprecated pre-framework shim from the bgutil 0.7.x era. It still patches the YouTube extractor (you'll see `[youtube+GetPOT]` in tracebacks) while registering zero providers. Nothing depends on it; it is a candidate for removal.

## ffmpeg

`ffmpeg.exe`, `ffprobe.exe` and `ffplay.exe` live in `frontend/` and are gitignored. Post-processing — audio extraction, container conversion, metadata and thumbnail embedding — fails without them.

## Running and probing the backend

```powershell
cd backend
py -3 manage.py runserver 9001 --noreload
```

Use `--noreload` when scripting against it: all download state is in module-level dicts, and an autoreload mid-download drops it.

Probe with **`localhost`, never `127.0.0.1`** — `ALLOWED_HOSTS` omits the latter and you'll get an HTTP 400 `DisallowedHost` that looks like an app bug:

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:9001/get_metadata/?link=<url-encoded link>"
```

`DEBUG = True`, so failures return a full HTML traceback and the console prints the Python traceback — read the console, it's far easier.

## Reading errors

Extractor failures surface as a `yt_dlp.utils.DownloadError` wrapping the real cause, which is usually the interesting part:

- `Unable to download API page` / SSL errors → network or TLS interception, not this repo.
- `Sign in to confirm you're not a bot` → PO token provider is down or version-mismatched.
- Format-not-available → the requested code isn't offered for that video; check the intersection logic in `choose_download`.

In the GUI, worker exceptions are caught by `ProcessThread.run`, formatted with the full traceback, and shown in a message box. That dialog text is the real traceback — ask for it rather than guessing.

## Version bumps

`yt-dlp` moves fast and YouTube breakage is normally fixed there. When bumping it:

1. Bump `yt-dlp` alone first, and verify a real download.
2. Keep the `bgutil-ytdlp-pot-provider` pip plugin and the IIS-hosted server on the **same** version as each other.
3. Watch for `PoTokenRequest` field changes — the bgutil plugin reads `video_webpage` and `internal_client_name` off it.
