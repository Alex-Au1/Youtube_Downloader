# Backend CI/CD

Used to update the backend code into the backend server.

Copies `backend/` into the IIS folder at `C:\inetpub\wwwroot\yt_download_backend`, then
restarts the application so the new code is actually picked up.

## Setup

Machine specific paths live in a gitignored `secrets.py`, the same convention the backend
uses. On a fresh clone:

```powershell
cd "Tools\BackendCICD\BackendCICD"
copy secrets_template.py secrets.py
```

Then fill it in:

```python
Deploy_Target = r"C:\inetpub\wwwroot\yt_download_backend"
App_Pool = None      # or "MyAppPool" to recycle it after every deploy
```

Without it the script stops and tells you what to create — it does not fall back to a
guessed path.

> `secrets.py` is loaded **by file path**, not with `import secrets`. `secrets` is a
> standard library module, and running `py -3 main.py` puts this folder first on
> `sys.path`, so a plain import would shadow the real one for the whole process. The
> backend only gets away with `from .secrets import ...` because that is a relative
> import inside a package.

## Usage

```powershell
cd "Tools\BackendCICD\BackendCICD"

py -3 main.py --dry-run                  # see what would change, touch nothing
py -3 main.py                            # deploy
py -3 main.py --app-pool "MyAppPool"     # deploy and recycle that pool (needs elevation)
```

**Always dry-run first.** It prints exactly which files are new, changed, protected or
orphaned, and writes nothing.

Command line flags beat `secrets.py`, which beats nothing at all.

| Flag | Effect |
| --- | --- |
| `--dry-run` | Report the plan, change nothing |
| `--target PATH` | Deploy somewhere other than `Deploy_Target` |
| `--source PATH` | Deploy from a different `backend/` folder |
| `--include-config` | Also overwrite `web.config` and `secrets.py` (off by default) |
| `--prune` | Delete server files that no longer exist locally |
| `--no-backup` | Skip backing up overwritten files |
| `--app-pool NAME` | Recycle that IIS app pool as well, overriding `App_Pool` |
| `--no-recycle` | Don't touch `web.config` afterwards |

## What it does and doesn't copy

Everything under `backend/` **except**:

- `venv/`, `__pycache__/`, `downloads/`, `.git/`, `*.pyc` — build artefacts and runtime data
- `db.sqlite3` — the dev database. The app doesn't use it, but overwriting a server file with a local one is never wanted
- `web.config` and `yt_downloader/secrets.py` — **environment specific**

The last pair is the important one. Those two are the files most likely to legitimately
differ between your machine and the server, so the server's copy always wins. The script
reports when they've diverged, so you can see it, but it won't revert a production setting
behind your back. Pass `--include-config` when you genuinely intend to push them.

The rule is exclusion-based rather than a list of files to copy, so a new module deploys
automatically without anyone remembering to add it here.

## Safety

- **Dry-run by request, verbose always.** Every file written, skipped, or deleted is printed.
- **Only changed files are written.** Contents are compared by hash, so an unchanged file is left alone and the output stays meaningful.
- **Overwritten files are backed up** to `Tools/BackendCICD/backups/<timestamp>/`, preserving the folder structure. That directory self-ignores via its own `.gitignore`.
- **Orphans are reported, never deleted** unless you pass `--prune`.
- **It refuses to run** if the source doesn't look like the backend, if the target doesn't exist, or if source and target are the same folder.
- **A failed copy stops the deploy** and tells you where the backups are, rather than continuing through a half-updated tree.

## Restarting the app

Copying `.py` files is not enough on its own — wfastcgi keeps the old modules loaded in
memory, so without a restart the server carries on running the previous code.

By default the script updates `web.config`'s timestamp, which makes IIS restart the
application. This needs no elevation. Passing `--app-pool NAME` also issues a real
`appcmd recycle apppool`, which is the more thorough option but requires an elevated
shell — if it fails, the script says so rather than pretending the deploy landed.

If neither restart works the script exits non-zero and warns that the old code is still
running.

## Stop your local server first

If IIS refuses to start the site with:

> The process cannot access the file because it is being used by another process

that message is about the **port**, not a file. It is what IIS reports (`0x80070020`)
when something else already holds the port the site binds. The usual culprit is a
`manage.py runserver` left over from local testing — the exact thing you were doing right
before deploying.

The script checks for this and warns, both in the plan and again after deploying:

```
warning: a Django development server is still running:
           pid 41484 holding port 9001
```

Stop it before starting the site:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*runserver*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

Kill **both** processes if you see two — Django's autoreloader runs a parent and a child,
and the child is the one holding the port.

A running dev server can also keep `__pycache__` folders open in the target, so they get
emptied but not removed. The script reports that honestly rather than claiming it cleared
them; empty `__pycache__` folders are harmless in themselves.

## After deploying

Check the site actually responds. Note the backend's `ALLOWED_HOSTS` does not include
`127.0.0.1`, so probe it via `localhost` or its LAN address — `127.0.0.1` returns a
confusing HTTP 400.
