# Frontend — the Tkinter app

Back to [root CLAUDE.md](../../CLAUDE.md). Cross-boundary contracts live in [Architecture](../architecture/CLAUDE.md).

Everything UI lives in one ~1600-line module, [youtube_va_downloader/youtube_downloader.py](../../frontend/youtube_va_downloader/youtube_downloader.py). Supporting modules:

| File | Role |
| --- | --- |
| `download_requests.py` | The only place that calls the backend. |
| `download_video.py` | Format enums, file-type tables, `DLUtils` (move file, write tags). |
| `format_display.py` | Number/date/filename formatting, and thumbnail fetching. |
| `set_up.py` | Reads and writes `setup.txt`. |
| `search_video.py` | **Dead code, but still imported.** See below. |

## The threading contract

**Read this before touching anything asynchronous.** It has been the source of real bugs.

Tkinter is single-threaded: only the main thread may touch widgets. Network work runs on long-lived worker threads, and results come back through a module-global dict.

Three workers are created once at import and reused for the life of the process:

```python
video_download_thread = ProcessThread(target=DownloadRequests.prepare_download, ..., key="download")
search_video_thread   = ProcessThread(target=search_videos,                     ..., key="search")
meta_data_thread      = ProcessThread(target=DownloadRequests.get_metadata,     ..., key="meta")
```

`ProcessThread` is a **restartable** worker: `run()` loops forever waiting on an `Event`, so one thread object serves many requests. Its return value is written to `processes[key]`, a module global.

The rules:

1. **Always start work with `thread.dispatch(*args)`.** Never call `start()` or `restart()` directly, and never assign `_callableArgs` by hand. `dispatch()` sets `_running = True`, clears `_error`, clears the stale `processes[key]`, and re-arms the completion event — all **on the GUI thread, before the worker can run**. Skipping it reintroduces a race where the poller sees a not-yet-started thread as a finished one, blocks the GUI in `join()`, and reads a missing or stale result.

2. **Always collect the result with `loading_page.check_running_thread(thread, callback, args, key)`.** It polls `_running` via `app.after(25, ...)`, animates the loading bar meanwhile, and on completion either shows the error dialog or calls `callback(processes[key], *args)`.

3. **In `ProcessThread.run()`, `_oneRunFinished.set()` must come before `_running = False`.** The poller treats "not `_running`" as its cue to `join()`, and `join()` waits on that event. Reverse the order and the GUI can block.

4. **`_error` must be cleared when handled.** It is sticky by nature: once set it stays set until something clears it. `check_running_thread` sets it back to `False` in the error branch. If that regresses, one transient network failure poisons that worker for the rest of the session — every later request pops the *original* stale traceback without ever running.

The call pattern, end to end:

```python
self.loading_page = LoadingPage(self.master, "loading...")
self.loading_page.pack_page()
meta_data_thread.dispatch(link)
self.loading_page.check_running_thread(meta_data_thread, self.choose_download, [...], "meta")
```

A separate plain `Thread` runs `WordWrap.wrap_search_text` continuously to re-wrap labels on resize. It is not a `ProcessThread` and does not use `processes`.

## Download options form

The questions are **declared as data** in `DOWNLOAD_STEPS` — a flat list of `DownloadStep(question, options, when=...)`. `DownloadOptionsForm` walks it, revealing the next applicable question as each is answered.

It is deliberately **not** a tree. The old version nested 15 `NestedRadioButton` instances five deep, with the `Video → best quality` and `Video → worst quality` subtrees byte-identical; quality is only an *answer* and never changes what is asked next. A flat list with predicates removes all of that duplication.

To add or change a question:

- Add one `DownloadStep` at the position it should be asked.
- `when` receives the answers collected so far and decides whether the step applies. It is evaluated only after all earlier steps have been resolved, so positional indexing inside it is safe.
- `options` is either a `{value: label}` dict, or the string `"audio"`/`"video"` to pull the per-video format set that is only known after metadata arrives.
- **Then update `prepare_download` in the backend**, because the answer list is a positional wire format. See [Architecture](../architecture/CLAUDE.md).

Re-answering a question truncates `query` and **destroys** every widget below it, rather than just unpacking them. That matters: unpacking leaves the old `StringVar`s holding selections that are no longer in `query`, so the UI can disagree with what gets sent.

The full flow is **questions → `RemixPanel` → folder chooser → Download button**, and `discard_below` tears down all three trailing stages.

## Remix panel

`RemixPanel` asks whether to remix and, if so, by how much: preset radios (Nightcore / Inverse Nightcore / Custom) plus a half-steps slider and a tempo slider. `get_remix()` returns the payload or `None`.

**It is deliberately not a `DownloadStep`.** Its answer must never enter `query`, which is a positional wire format — it is sent as a separate `remix` field instead. See [Architecture](../architecture/CLAUDE.md).

The pitch slider hides its own number (`showvalue = 0`) and shows a musical interval instead — "maj 3rd above", "dim 5th below" — from the `MUSIC_INTERVALS` table via `interval_name()`. The tempo slider is paired with an `Entry` for typing an exact decimal, following the same `Frame(bg="black")` + `Entry` idiom as the settings dialog.

Four interactions worth knowing before editing it:

- **A `Scale`'s `command` only fires on user interaction, NOT when its linked variable is written programmatically.** Readouts that must follow a preset therefore hang off `trace_add("write", ...)` on the variables, not off the Scale's `command`. This is easy to get wrong and hard to notice: a test that only sets variables will pass against a broken `command` wiring, because nothing fires either way.
- **Presets and sliders would chase each other.** Selecting a preset writes the slider variables, whose trace would flip the preset to Custom. `applying_preset` guards the programmatic writes. Remove it and presets become unselectable.
- **Traces are added last in `__init__`**, after the defaults are set, so initialising the panel doesn't register as a user edit.
- **The folder chooser is only built once.** `remix_answered` checks `folder_frame is None` first, so toggling the remix on and off doesn't discard a folder the user already picked.

`interval_name` is a 13-entry lookup rather than the arithmetic in Haku_Bot's `get_relative_interval`. That version mislabels 9 and 11 half steps, and every descending interval past −8, because it tests the *signed* half-step count against the perfect 4th instead of the absolute distance. The slider spans one octave either way, so a table covers every case and cannot drift.

Slider bounds mirror the backend's and are fixed by ffmpeg's `atempo` limits — don't widen them on this side alone. Neutral settings (0 half steps, 1.0 speed) return `None` rather than a no-op remix, so no pointless ffmpeg pass runs.

## Thumbnails

`FormatUtils.process_image` fetches and resizes. It must check `status_code` explicitly — i.ytimg.com answers a missing thumbnail size with HTTP 404 **and a valid 120×90 grey placeholder JPEG**, so PIL decodes it happily and nothing raises. On failure it retries at `hqdefault.jpg` (the one size every video has) and falls back to a flat grey tile so a single dead thumbnail can't take down a whole page of results.

Requests here carry a timeout. Without one, a hung connection wedges the search worker forever and the loading animation spins with no way out.

`PhotoImage` objects must be kept referenced or Tk garbage-collects them and shows blank images — that is what the module-global `photo_lst` dict is for. Search results are keyed by index, download pages by `f"d{key}"`.

## `search_video.py` is dead but load-bearing

Its `search_youtube_video` — a hand-rolled brace-matching JSON parser from the `youtube-search-python` era — is **never called**. Search goes through `DownloadRequests.search_youtube_video`, a different function that calls the backend.

But `youtube_downloader.py` still does `from .search_video import search_youtube_video` at the top, and `search_video.py` in turn does `from youtubesearchpython import VideosSearch`. So:

- **`youtube-search-python` is a hard install dependency held only by dead code.** Removing the package breaks startup with an `ImportError`.
- Deleting `search_video.py` requires also deleting that import line. Do both or neither.

Don't extend or refactor this module.

## Page caching

`displayed_search_pages` and `download_pages_lsts` cache `ScrollFrame`s so navigating back doesn't refetch. `download_pages_lsts` is keyed by video id, except for direct-link downloads which use `-1` and are always rebuilt. Clearing these is what `clear_search` and `return_home` do.

## Settings

`setup.txt` sits next to `exe_main.py` and is three lines: results per search, results per page, backend URL. Managed by `SetupFile` in `set_up.py`; edited in-app through the Settings dialog. It is gitignored, so a fresh clone regenerates it from `set_up.default` — whose `host_url` default is `http://192.168.1.72:9001`, a LAN address that will not work on a fresh machine. Expect to fix that first.

## Packaging

Built with PyInstaller via `exe_spec.spec` / `youtube_downloader.spec`. `ffmpeg.exe`/`ffprobe.exe` sit in `frontend/` and are gitignored, so they must be restored manually on a fresh clone; post-processing fails without them.
