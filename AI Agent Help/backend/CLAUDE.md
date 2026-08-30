# Backend — Django + yt-dlp

Back to [root CLAUDE.md](../../CLAUDE.md). Cross-boundary contracts live in [Architecture](../architecture/CLAUDE.md).

A deliberately thin Django project. Only four files matter:

| File | Contents |
| --- | --- |
| [yt_downloader/views.py](../../backend/yt_downloader/views.py) | All 7 endpoints, as `@classmethod`s on `DownloaderView`. Thin — they unpack the request and delegate. |
| [yt_downloader/models.py](../../backend/yt_downloader/models.py) | Everything real: the `yt-dlp` wrapper, format tables, progress tracking. |
| [yt_downloader/urls.py](../../backend/yt_downloader/urls.py) | Route table. |
| [src/settings.py](../../backend/src/settings.py) | `DEBUG = True`, the `ALLOWED_HOSTS` list. |

**`models.py` contains no Django models.** `YoutubeDownload` is a plain class. `migrations/` holds only `__init__.py`, and `yt_downloader` is absent from `INSTALLED_APPS`. Don't reach for the ORM or `makemigrations` — nothing here is persisted.

## The download pipeline

`prepare_download(video, options, folder)` → `download_video(...)` → background thread → `_download_video` → `__download_video`.

**`prepare_download`** translates the frontend's answer list into `yt-dlp` vocabulary. It produces:

- `format` — a `yt-dlp` format selector string, e.g. `"bestvideo+bestaudio/best"` or `"137+bestaudio/best"`.
- `download_type` — a dict describing the desired output, `{"audio": ...}` and/or `{"video": ...}`, used to decide post-processing.
- `file_type` — `"audio"`, `"video"` or `"video+audio"`, which drives the progress messages.

The exact strings it matches on are the wire format — see [Architecture](../architecture/CLAUDE.md) before editing.

**`download_video`** assembles `ydl_opts`, then:

- Picks post-processors. `FFmpegExtractAudio` for audio-only with a specific codec; `FFmpegVideoConvertor` for a specific container. Always appends `FFmpegMetadata` and `EmbedThumbnail`.
- Embeds a thumbnail only when the output extension is in `THUMBNAIL_EMBED_FORMATS`. **That list must stay in sync with yt-dlp's `EmbedThumbnailPP`**, which supports `mp3`, `mkv`/`mka`, `m4a`/`mp4`/`m4v`/`mov` and `ogg`/`opus`/`flac`. A format missing from the list never gets `writethumbnail` set, so no thumbnail is downloaded and `EmbedThumbnail` silently finds nothing to embed — the cover just comes out empty with no error. `opus` and `flac` were missing for exactly this reason. Note `audio_filetypes` maps `ogg` to the *codec* name `vorbis`, so both spellings are in the list.
- When quality is best/worst rather than an explicit code, it makes **an extra `get_metadata` call** just to learn the resulting extension. That is a second network round trip per download.
- Creates a per-download temp folder `Download_Folder/<download_id>` and sets both `paths.home` and `paths.temp` to it.
- Starts a daemon `Thread` and returns immediately.

`_download_with_thumbnail_fallback` retries once without the thumbnail, since embedding genuinely fails for some videos. Two things there are deliberate:

- It only retries when `writethumbnail` was actually set. Otherwise the retry would be identical, so it re-raises the real error instead. (It used to `pop` that key without a default, which raised `KeyError` and masked every failure for formats that never set it.)
- It drops `EmbedThumbnail` **by key**, not by list position. It is not always last.

## Failed downloads must not hang the client

`_download_video` runs on its own thread and `download_stream` waits on `Finished_Download`. If an exception escapes that thread, `Finished_Download` is never set and the SSE stream loops forever — the frontend spins with no way out.

So the thread catches everything and records it in the module-level `Download_Error` dict. `download_stream` checks that alongside `Finished_Download` and emits `{"type": "error", "data": ...}` before closing; the frontend raises on that event so the reason lands in the error dialog.

**Any new code path that can leave a download unfinished must set `Download_Error`,** or it reintroduces the hang.

## Progress reporting

`download_hook` is a `yt-dlp` progress hook. It writes a formatted string into `Download_Progress[id]`. It never returns anything.

`video+audio` downloads invoke the hook for **two** passes; `Download_No[id]` tracks which one, so the UI can say "Video Part" then "Audio Part" then "Now Converting...".

The strings from `yt-dlp` contain ANSI colour codes; `FormatUtils.remove_ansi_codes` strips them. If progress text ever renders with escape junk, that's the missing call.

## Remix (pitch / tempo)

`RemixOptions` + `Remixer` in `models.py`. Applied as **one extra ffmpeg pass in `_download_video`**, after `yt-dlp` finishes and before the file is published to `Finished_Download`.

The filter chain is ported from the jukebox in `Haku_Bot/search/music.py`:

```
pitch       = 2 ** (half_steps / 12)          equal temperament
asetrate    = rate * pitch                    shifts pitch AND speed together
atempo      = 1 / pitch                       cancels the speed change -> pure pitch shift
atempo      = speed                           applies the wanted tempo
aresample   = rate                            (added here; see below)
```

`aresample` is not in the original, which streams to Discord and lets it resample. Writing a file, it keeps the output's declared sample rate equal to the input's rather than the asetrate-inflated one.

**The ±12 half-step and 0.5–2.0 speed bounds are load-bearing, not taste.** `atempo` only accepts 0.5–2.0 per instance. At ±12 half steps `pitch` is 0.5/2.0, so the `1/pitch` correction lands exactly on those limits. Widening either range means emitting several chained `atempo` filters. `RemixOptions.__init__` clamps to enforce this.

Other things `Remixer` gets right, which are easy to regress:

- **Cover art is not video.** Audio downloads carry an embedded thumbnail as an `attached_pic` stream. `has_moving_video` ignores those, so the still is never fed through `setpts`.
- **Cover art has to be re-embedded, not copied through.** ffmpeg can *read* cover art out of containers it cannot *write* it back into — opus is the case that bites, where the cover is a `METADATA_BLOCK_PICTURE` vorbis comment and the muxer has no video support at all, so `-c:v copy` silently produces a coverless file. `apply` therefore extracts the cover, remixes with `-vn`, and re-embeds afterwards via yt-dlp's own `EmbedThumbnailPP` — the same code that embedded it originally, so every container is handled the way it expects. Verified for mp3, m4a, opus, flac and ogg.
- **Pitch-only changes copy the video stream.** `setpts` forces a re-encode, so it's only used when `changes_tempo()`. A tempo change on a long video *is* a full re-encode and will be slow.
- **Every failure returns the original path.** Missing ffprobe, a non-zero ffmpeg exit, a failed swap — all degrade to the un-remixed file. A plain download beats a dead one.
- Sample rate is probed per file rather than assumed; `DEFAULT_SAMPLE_RATE` is only the fallback.

Progress shows `"Remixing..."` during the pass. That works because `Finished_Download[id]` stays `None` until after the remix, so the SSE stream keeps streaming rather than sending `done`.

## Format code tables

YouTube identifies formats by numeric code (itag): `"137"` = mp4 1080p H.264. One table, `VIDEO_FORMAT_CODES`, maps each itag to `(label, extension)`; `code_display` and `extension_display` are derived from it.

**This table is duplicated verbatim** in `backend/yt_downloader/models.py` and `frontend/youtube_va_downloader/download_video.py`. Edit both or they desync — nothing enforces it.

Which formats are offered for a given video is the intersection of `VideoCodes.get_all_codes()` with what that video's metadata reports, computed frontend-side in `choose_download`. **An itag missing from the table is invisible in the dropdown**, however available it actually is — that is how VP9 and AV1 came to be unreachable.

Covered now: DASH H.264 mp4, DASH VP9 webm, AV1 mp4, and the HLS itags. Deliberately absent are itags YouTube stopped serving — 22 and 17 (dropped 2024), 5, 43, 36, and the throttled muxed 18.

### The real fix, if this ever needs maintenance

**Current yt-dlp no longer keeps an itag table at all.** It was deleted; the extractor now reads `height`/`width`/`fps`/`ext`/`vcodec`/`acodec`/`tbr` straight out of YouTube's `streamingData`, and the only itags it still mentions are `'17'` and `'22'` as quality de-prioritisation hints.

Those same fields are already present on every entry of the `formats` list this backend fetches. Building the dropdown from them would delete `VIDEO_FORMAT_CODES`, `code_display` and `extension_display` outright, remove the front/back duplication, and pick up new codecs automatically. Prefer that over extending the list.

If you do need a reference list, note that the itag gists online disagree with each other and are frequently years stale — one widely-linked gist still lists AV1 as 330–337, which is wrong. yt-dlp's own historical `_formats` table (still present in the old `backend/venv` copy, and in yt-dlp's git history) is the trustworthy source; that is where the current entries came from.

## Search

`get_youtube_search` uses `yt-dlp` with `extract_flat: True` against `ytsearch<N>:<query>`, then reshapes each entry into the dict the frontend expects (`title`, `channel.name`, `viewCount.text`, `thumbnails[]`, `link`, ...). That shape mimics the old `youtube-search-python` output the frontend was originally written against.

**Thumbnails:** prefer what `yt-dlp` reports. Only construct an `i.ytimg.com` URL as a last resort, and only `hqdefault.jpg`. Do **not** use `hq720.jpg` or `maxresdefault.jpg` — they 404 for videos without a 720p rendition, and i.ytimg.com serves those 404s with a *valid* 120×90 grey placeholder JPEG, so the failure is invisible and shows up as a blurry grey box in the UI.

## Config

- **`secrets.py`** (gitignored) defines `Download_Folder`, the server-side temp root. `secrets_template.py` is the committed stub.
- **`Extractor_Args`** pins the PO token provider to `http://127.0.0.1:9002`. `add_po_token_provider` also sets `js_runtimes` (node) and `remote_components` (`ejs:github`) on every `yt-dlp` call. See [Environment](../environment/CLAUDE.md).
- **`web.config`** is a leftover Azure/IIS FastCGI template referencing `C:\inetpub\wwwroot\yt_download_backend`. It is not used by `runserver` and its paths are stale — ignore it unless you are deliberately setting up IIS hosting.
