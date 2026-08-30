"""
Deploys the locally tested backend to the IIS folder.

    py -3 main.py --dry-run                  show what would change, touch nothing
    py -3 main.py                            deploy
    py -3 main.py --app-pool "MyAppPool"     deploy and recycle that pool

Everything under backend/ is copied except build artefacts (see EXCLUDED_*) and the
environment specific files in PROTECTED, whose server copy is left alone. Only files
whose contents actually differ are written, and anything overwritten is backed up first.
"""
import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


#machine specific settings live beside this script, in a gitignored secrets.py
SECRETS_PATH = Path(__file__).resolve().parent / "secrets.py"
TEMPLATE_PATH = Path(__file__).resolve().parent / "secrets_template.py"

#never deployed: virtualenvs, caches, downloaded media, the dev database
EXCLUDED_DIRS = {"venv", "__pycache__", ".git", ".vs", "node_modules", "downloads"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {"db.sqlite3", ".gitignore"}

#environment specific. The server's copy wins unless --include-config is passed, so a
#  deploy can never silently revert a production setting
PROTECTED = {"web.config", "yt_downloader/secrets.py"}

#files that must exist in the source for it to be a plausible backend
SANITY_FILES = ("manage.py", "yt_downloader/models.py", "src/settings.py")


def repo_backend() -> Path:
    #this file lives at <repo>/Tools/BackendCICD/BackendCICD/main.py
    return Path(__file__).resolve().parents[3] / "backend"


def load_secrets():
    """Reads secrets.py by path, rather than importing it.

    'secrets' is a standard library module and this script's own folder sits first on
    sys.path, so a plain `import secrets` here would shadow the real one for everything
    in the process. The backend only gets away with `from .secrets import ...` because
    that is a relative import inside a package.
    """
    if (not SECRETS_PATH.exists()):
        return None

    spec = importlib.util.spec_from_file_location("backend_cicd_secrets", SECRETS_PATH)
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"error: could not read {SECRETS_PATH}: {e}")
        return None

    return module


def setting(secrets, name):
    return getattr(secrets, name, None) if (secrets is not None) else None


def deployable_files(root: Path):
    """every path under 'root', relative and posix style, that belongs on the server"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for name in filenames:
            if (name in EXCLUDED_NAMES or Path(name).suffix in EXCLUDED_SUFFIXES):
                continue

            yield (Path(dirpath) / name).relative_to(root).as_posix()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_plan(source: Path, target: Path, include_config: bool) -> dict:
    plan = {"new": [], "changed": [], "unchanged": [], "protected": [], "orphans": []}

    source_files = sorted(deployable_files(source))

    for rel in source_files:
        src_file, dst_file = source / rel, target / rel

        if (rel in PROTECTED and not include_config):
            #still worth reporting when the two have drifted apart
            diverged = dst_file.exists() and digest(src_file) != digest(dst_file)
            plan["protected"].append((rel, diverged, not dst_file.exists()))
            continue

        if (not dst_file.exists()):
            plan["new"].append(rel)
        elif (digest(src_file) != digest(dst_file)):
            plan["changed"].append(rel)
        else:
            plan["unchanged"].append(rel)

    #files on the server that no longer exist locally
    known = set(source_files)
    for rel in sorted(deployable_files(target)):
        if (rel not in known and rel not in PROTECTED):
            plan["orphans"].append(rel)

    return plan


def copy_file(source: Path, target: Path, rel: str, backup_dir):
    src_file, dst_file = source / rel, target / rel

    if (backup_dir is not None and dst_file.exists()):
        backup_path = backup_dir / rel
        backup_path.parent.mkdir(parents = True, exist_ok = True)
        shutil.copy2(dst_file, backup_path)

    dst_file.parent.mkdir(parents = True, exist_ok = True)
    shutil.copy2(src_file, dst_file)


def clear_pycache(target: Path):
    """Clears stale bytecode, which is written by the app pool user and can outlive the
    source it came from.

    Returns (removed, kept). A folder whose files are deleted but which itself survives
    is counted as kept, not removed: Windows refuses to remove a directory something
    still has open, and reporting that as a success hides a running process.
    """
    removed, kept = 0, []

    for dirpath, dirnames, filenames in os.walk(target):
        if ("venv" in Path(dirpath).parts):
            continue

        for name in list(dirnames):
            if (name != "__pycache__"):
                continue

            cache = Path(dirpath) / name
            shutil.rmtree(cache, ignore_errors = True)
            dirnames.remove(name)

            if (cache.exists()):
                kept.append(cache)
            else:
                removed += 1

    return removed, kept


def report_pycache(target: Path):
    removed, kept = clear_pycache(target)

    if (removed):
        print(f"  cleared {removed} __pycache__ folder(s)")

    if (kept):
        print(f"  ! {len(kept)} __pycache__ folder(s) could not be removed, "
              "something still has them open:")
        for cache in kept:
            print(f"      {cache}")


#a leftover `manage.py runserver` is the usual reason a freshly deployed site refuses to
#  start, so it is worth naming explicitly
DEV_SERVER_QUERY = (
    "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
    "Where-Object { $_.CommandLine -like '*manage.py*runserver*' } | "
    "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
)


def parse_dev_server(line: str):
    """turns one 'pid<TAB>commandline' row into (pid, port or None)"""
    pid, _, command = line.partition("\t")

    if (not pid.strip().isdigit()):
        return None

    #runserver takes an optional [addr:]port
    match = re.search(r"runserver\s+(?:\S+:)?(\d+)", command)
    return (pid.strip(), match.group(1) if (match) else None)


def running_dev_servers():
    """Django development servers currently running, as a list of (pid, port)"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", DEV_SERVER_QUERY],
            capture_output = True, timeout = 60)
    except (OSError, subprocess.SubprocessError):
        return []

    if (result.returncode):
        return []

    found = []
    for line in result.stdout.decode("utf-8", errors = "replace").splitlines():
        parsed = parse_dev_server(line)

        if (parsed is not None):
            found.append(parsed)

    return found


def warn_about_dev_servers(dev_servers):
    if (not dev_servers):
        return

    print()
    print("warning: a Django development server is still running:")
    for pid, port in dev_servers:
        where = f" holding port {port}" if (port) else ""
        print(f"           pid {pid}{where}")

    print()
    print("         IIS cannot bind a port that already belongs to another process. If the")
    print("         site uses one of these, starting it fails with 'The process cannot")
    print("         access the file because it is being used by another process' -- which")
    print("         means the PORT, not a file.")
    print()
    print("         Stop it before starting the site:")
    print("           Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |")
    print("             Where-Object { $_.CommandLine -like '*runserver*' } |")
    print("             ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")


def recycle_app_pool(name: str) -> bool:
    appcmd = Path(os.environ.get("WINDIR", r"C:\Windows")) / "system32" / "inetsrv" / "appcmd.exe"

    if (not appcmd.exists()):
        print(f"  ! appcmd.exe not found at {appcmd}")
        return False

    try:
        result = subprocess.run([str(appcmd), "recycle", "apppool", f"/apppool.name:{name}"],
                                capture_output = True, timeout = 120)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  ! could not run appcmd: {e}")
        return False

    if (result.returncode):
        message = (result.stderr or result.stdout).decode("utf-8", errors = "replace").strip()
        first_line = message.splitlines()[0] if (message) else "unknown error"
        print(f"  ! recycling '{name}' failed: {first_line}")
        print("    (recycling an app pool needs an elevated shell)")
        return False

    print(f"  recycled app pool '{name}'")
    return True


def touch_web_config(target: Path) -> bool:
    """IIS restarts an application when its web.config changes, which is how the new code
    gets picked up without an elevated shell. Only the timestamp is altered"""
    config = target / "web.config"

    if (not config.exists()):
        print("  ! no web.config in the target, cannot nudge IIS")
        return False

    try:
        os.utime(config, None)
    except OSError as e:
        print(f"  ! could not touch web.config: {e}")
        return False

    print("  touched web.config to trigger an application restart")
    return True


def report(plan: dict, args, source: Path, target: Path):
    print(f"source : {source}")
    print(f"target : {target}")
    print()

    print(f"{'new':>9}: {len(plan['new'])}")
    for rel in plan["new"]:
        print(f"           + {rel}")

    print(f"{'changed':>9}: {len(plan['changed'])}")
    for rel in plan["changed"]:
        print(f"           ~ {rel}")

    print(f"{'unchanged':>9}: {len(plan['unchanged'])}")

    if (plan["protected"]):
        print(f"{'protected':>9}: {len(plan['protected'])}  (left as the server has them)")
        for rel, diverged, missing in plan["protected"]:
            if (missing):
                note = "  <-- MISSING on the server"
            elif (diverged):
                note = "  <-- differs from local"
            else:
                note = ""
            print(f"           = {rel}{note}")

    if (plan["orphans"]):
        action = "will be deleted" if (args.prune) else "left alone, pass --prune to remove"
        print(f"{'orphans':>9}: {len(plan['orphans'])}  ({action})")
        for rel in plan["orphans"]:
            print(f"           - {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description = "Deploy the backend to the IIS folder.")
    parser.add_argument("--target", type = Path, default = None,
                        help = "IIS folder to deploy into (default: Deploy_Target from secrets.py)")
    parser.add_argument("--source", type = Path, default = None,
                        help = "backend folder to deploy from (default: this repo's backend/)")
    parser.add_argument("--dry-run", action = "store_true",
                        help = "report what would change without writing anything")
    parser.add_argument("--include-config", action = "store_true",
                        help = f"also overwrite the protected files: {', '.join(sorted(PROTECTED))}")
    parser.add_argument("--prune", action = "store_true",
                        help = "delete server files that no longer exist locally")
    parser.add_argument("--no-backup", action = "store_true",
                        help = "do not back up overwritten files")
    parser.add_argument("--app-pool", default = None,
                        help = "also recycle this IIS app pool (default: App_Pool from secrets.py)")
    parser.add_argument("--no-recycle", action = "store_true",
                        help = "do not touch web.config afterwards")
    args = parser.parse_args()

    secrets = load_secrets()

    #command line beats secrets.py, which beats nothing at all
    target_setting = args.target or setting(secrets, "Deploy_Target")
    app_pool = args.app_pool or setting(secrets, "App_Pool")

    if (not target_setting):
        if (secrets is None):
            print(f"error: no secrets.py found at {SECRETS_PATH}")
            print(f"       copy {TEMPLATE_PATH.name} to secrets.py and fill in Deploy_Target,")
            print("       or pass --target")
        else:
            print(f"error: Deploy_Target is not set in {SECRETS_PATH}")
            print("       fill it in, or pass --target")

        return 1

    source = (args.source or repo_backend()).resolve()
    target = Path(target_setting).resolve()

    if (not source.is_dir()):
        print(f"error: source folder does not exist: {source}")
        return 1

    missing = [f for f in SANITY_FILES if not (source / f).exists()]
    if (missing):
        print(f"error: {source} does not look like the backend (missing {', '.join(missing)})")
        return 1

    if (not target.is_dir()):
        print(f"error: target folder does not exist: {target}")
        print("       create it first, or pass --target")
        return 1

    if (source == target):
        print("error: source and target are the same folder")
        return 1

    plan = build_plan(source, target, args.include_config)
    report(plan, args, source, target)

    dev_servers = running_dev_servers()
    warn_about_dev_servers(dev_servers)

    pending = plan["new"] + plan["changed"]
    prunable = plan["orphans"] if (args.prune) else []

    print()
    if (args.dry_run):
        print(f"dry run: {len(pending)} file(s) would be written, "
              f"{len(prunable)} deleted. Nothing was changed.")
        return 0

    if (not pending and not prunable):
        print("nothing to deploy, the server is already up to date.")

        #still clear caches, since a previous run may not have
        report_pycache(target)

        return 0

    backup_dir = None
    if (not args.no_backup and (plan["changed"] or prunable)):
        #milliseconds included so two deploys in the same second do not share a folder
        #  and overwrite each other's saved copies
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        backup_dir = Path(__file__).resolve().parent.parent / "backups" / stamp
        backup_dir.mkdir(parents = True, exist_ok = True)

        #keep the backups out of source control without editing the repo's .gitignore
        (backup_dir.parent / ".gitignore").write_text("*\n", encoding = "utf-8")

    written = 0
    for rel in pending:
        try:
            copy_file(source, target, rel, backup_dir)
            written += 1
        except OSError as e:
            print(f"  ! failed to copy {rel}: {e}")
            print("    deploy stopped; the server is in a partially updated state")
            if (backup_dir is not None):
                print(f"    the previous versions are in {backup_dir}")
            return 1

    print(f"  wrote {written} file(s)")

    deleted = 0
    for rel in prunable:
        dst_file = target / rel
        try:
            if (backup_dir is not None):
                backup_path = backup_dir / rel
                backup_path.parent.mkdir(parents = True, exist_ok = True)
                shutil.copy2(dst_file, backup_path)

            dst_file.unlink()
            deleted += 1
        except OSError as e:
            print(f"  ! failed to delete {rel}: {e}")

    if (deleted):
        print(f"  deleted {deleted} orphaned file(s)")

    if (backup_dir is not None):
        print(f"  backed up the previous versions to {backup_dir}")

    report_pycache(target)

    print()
    print("restarting the application:")

    recycled = False
    if (app_pool):
        recycled = recycle_app_pool(app_pool)

    if (not args.no_recycle):
        touched = touch_web_config(target)
        recycled = recycled or touched

    if (not recycled):
        print("  ! the app was NOT restarted, so it is still running the old code")
        print("    recycle the app pool from IIS Manager, or rerun with --app-pool NAME")
        return 1

    #repeated here because this is the point it actually bites: the files are in place,
    #  and the next thing to fail will be the site refusing to start
    if (dev_servers):
        print()
        print("  ! reminder: stop the development server above before starting the site")

    print()
    print("done. Check the site responds before considering the deploy finished.")
    return 0


if (__name__ == "__main__"):
    sys.exit(main())
