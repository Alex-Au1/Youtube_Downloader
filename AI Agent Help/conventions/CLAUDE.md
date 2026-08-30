# Conventions — style and how to verify a change

Back to [root CLAUDE.md](../../CLAUDE.md).

## Match the surrounding style

This codebase has its own idiom. It is consistent, and consistency beats your preferences here.

- **Conditions are parenthesised:** `if (not folder):`, `elif (options[1] == "best quality"):`. Keep it.
- **Comments are lowercase `#` lines above the thing they describe.** Older functions use a `'''...'''` block above the `def` with an informal type signature. Both are fine; match the file you're in.
- `snake_case` for functions and variables, `Capitalized_Snake` for module-level mutable globals (`Download_Progress`, `Last_Progress`, `Host_Url`).
- Type hints appear in newer code and are absent in older code. Adding them to code you touch is welcome; a hint-only sweep is not.

**Do not reformat wholesale.** No project-wide linter or formatter is configured, and a reformat buries the real change in noise.

## Bare `except:` — leave the deliberate ones

There are bare `except:` blocks that are genuinely load-bearing fallbacks:

- `_download_video` retries without `writethumbnail` when embedding fails.
- `prepare_download` uses `try: options[4] except: options[3]` to distinguish the two video shapes.
- `root.iconbitmap(...)` tolerates a missing icon.

Don't "fix" these into narrow handlers without checking what actually throws. Do add proper handling to genuinely new code.

## Verifying a change

There is no test suite and no test runner. Nothing here is wired to CI. Verify in this order.

**1. Compile.** Catches the majority of edit mistakes instantly:

```powershell
py -3 -m py_compile "frontend\youtube_va_downloader\youtube_downloader.py"
```

**2. Drive the logic headlessly.** This is the highest-value technique in this repo and it is not obvious, so it is worth spelling out.

Importing the frontend module creates a `Tk()` root and the whole `Application` as an import side effect (the module-level `if (__name__ != "__main__"):` block). That means UI classes can be imported and driven from a plain script without ever calling `mainloop()`:

```python
import sys, tkinter
sys.path.insert(0, r"...\Youtube_Downloader\frontend")
from youtube_va_downloader.youtube_downloader import DownloadOptionsForm, DOWNLOAD_STEPS

root = tkinter.Tk(); root.withdraw()
form = DownloadOptionsForm(root, DOWNLOAD_STEPS, {"audio": {...}, "video": {...}},
                           video={"duration": "3:00"}, page_found=0)
form.render()

# a Radiobutton click is exactly: set that question's var, then fire its command
form.questions[0]["var"].set("Audio")
form.question_answered(0)

assert form.query == ["Audio"]
```

The same trick works for `ProcessThread`: `dispatch()` it with a stub callable, poll `_running`, and assert on `processes[key]`.

Write these scripts to the scratch directory, not into the repo — there is no `tests/` and adding a stray one at the root will look like project structure.

**Two cautions learned the hard way:**

- A helper that fires a click must target the *right* question. Setting a `StringVar` to a value that question doesn't offer silently succeeds in a test (real radio buttons can't do it) and produces nonsense that looks like a product bug. Assert the value is in that step's options before setting it.
- **Driving a widget by writing its variable is not the same as using it.** A `Scale`'s `command` fires only on real interaction, so a test that sets the variable exercises neither the command nor any guard around it — and passes whether the wiring works or not. Assert on the *observable result* (the label text, the entry contents) rather than on the callback having run.
- **Test one media format and you have tested one media format.** Cover art is an `attached_pic` stream in mp3/m4a/flac but a `METADATA_BLOCK_PICTURE` comment in opus; tags sit on the container for mp3/m4a but on the *stream* for ogg/opus. A check that reads only `format_tags` reports a false loss for half of them. When asserting on media, cover every format the app actually offers, and confirm the assertion is looking where that format stores the thing.

**3. Run the real thing** for anything touching layout, or any change where the two processes have to agree. Backend first:

```powershell
cd backend && py -3 manage.py runserver 9001
cd frontend && py -3 exe_main.py
```

## Changes that span both halves

The download-options list is a positional wire format ([Architecture](../architecture/CLAUDE.md)). Adding, removing or renaming a question means editing `DOWNLOAD_STEPS` **and** `prepare_download` together. There is no validation on either side — a mismatch yields a wrong download, not an error. Exercise all three paths (audio, video+audio, video-only) after any such change.

## What not to bother with

- `search_video.py` is dead code — a hand-rolled brace-matching JSON parser from before search moved to the backend. Don't extend or refactor it. Note it is still *imported*, so it can't simply be deleted; see [Frontend](../frontend/CLAUDE.md).
- `backend/web.config` is a stale Azure FastCGI template with wrong paths. Irrelevant to `runserver`.
- `db.sqlite3` is unused; there are no ORM models and no migrations to run.
- `backend/requirements.txt` describes the dead venv, not the live environment.
