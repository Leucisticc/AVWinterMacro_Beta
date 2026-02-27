import io
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen


MAIN_FOLDER = Path(__file__).resolve().parents[1]

# Change these for your repo/release setup.
OWNER = "loxerex"
REPO = "Winter-Normal-Macro"
ASSET_NAME = "Winter-Normal-Macro.zip"
VERSION_FILE = "version.json"  # optional; falls back to Winter_Event.py VERSION_N

# Only these paths are replaced during update.
# Keep Settings/Winter_Event.json OUT so user settings are preserved.
UPDATE_WHITELIST = [
    "Winter_Event.py",
    "webhook.py",
    "Position.py",
    "Tools/",
    "Utility/",
    "Resources/",
    "requirements.txt",
    VERSION_FILE,
]

REQUIRED_PATHS = [
    "Winter_Event.py",
    "webhook.py",
    "Position.py",
    "Settings/Winter_Event.json",
    "Utility/mouseDebugging.py",
    "Utility/SettingsHelper.py",
    "Tools/avMethods.py",
    "Tools/botTools.py",
    "Tools/winTools.py",
    "Resources",
    "tesseract",
]


def _is_whitelisted(rel_path: str) -> bool:
    rel_path = rel_path.replace("\\", "/")
    for item in UPDATE_WHITELIST:
        item = item.replace("\\", "/")
        if item.endswith("/"):
            if rel_path.startswith(item):
                return True
        else:
            if rel_path == item:
                return True
    return False


def _read_local_version(project_root: Path) -> str:
    p = project_root / VERSION_FILE
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ver = str(data.get("version", "")).strip()
            if ver:
                return ver
        except Exception:
            pass

    winter_file = project_root / "Winter_Event.py"
    if winter_file.exists():
        try:
            txt = winter_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"VERSION_N\s*=\s*['\"]([^'\"]+)['\"]", txt)
            if m:
                return m.group(1).strip()
        except Exception:
            pass

    return "0.0.0"


def _github_latest_release() -> dict:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "WinterFileChecker",
        },
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "WinterFileChecker"})
    with urlopen(req, timeout=90) as response:
        return response.read()


def _backup(project_root: Path) -> Path:
    backup_dir = project_root / ".backup_before_update"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _is_safe_member(name: str) -> bool:
    p = Path(name)
    if p.is_absolute():
        return False
    parts = p.parts
    if any(part in ("..", "") for part in parts):
        return False
    return True


def _extract_zip_safely(zip_bytes: bytes, out_dir: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if not _is_safe_member(info.filename):
                raise RuntimeError(f"Unsafe zip entry blocked: {info.filename}")
        zf.extractall(out_dir)


def _find_source_root(extracted_dir: Path) -> Path:
    entries = list(extracted_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted_dir


def _copy_whitelisted(src_root: Path, dst_root: Path, backup_dir: Path) -> list[Path]:
    touched: list[Path] = []
    for src_path in src_root.rglob("*"):
        if src_path.is_dir():
            continue
        rel = src_path.relative_to(src_root).as_posix()
        if not _is_whitelisted(rel):
            continue

        dst_path = dst_root / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if dst_path.exists():
            backup_path = backup_dir / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst_path, backup_path)

        shutil.copy2(src_path, dst_path)
        touched.append(dst_path)
    return touched


def _restore_from_backup(project_root: Path, backup_dir: Path, touched_files: list[Path]) -> None:
    for dst_path in touched_files:
        rel = dst_path.relative_to(project_root)
        backup_path = backup_dir / rel
        if backup_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, dst_path)


def _normalize_version(version_text: str):
    text = (version_text or "").strip().lower()
    nums = [int(x) for x in re.findall(r"\d+", text)]
    nums = (nums + [0, 0, 0])[:3]

    if "alpha" in text:
        stage = 0
    elif "beta" in text:
        stage = 1
    elif "rc" in text:
        stage = 2
    else:
        stage = 3
    return (nums[0], nums[1], nums[2], stage)


def _is_remote_newer(local_ver: str, remote_ver: str) -> bool:
    return _normalize_version(remote_ver) > _normalize_version(local_ver)


def _run_file_check() -> None:
    print("Running file check..")
    print(f"Home folder: {MAIN_FOLDER}")
    for rel in REQUIRED_PATHS:
        path = MAIN_FOLDER / rel
        print(f"{rel}, Exists: {path.exists()}")


def _pick_asset_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            return asset.get("browser_download_url")
    return release.get("zipball_url")


def _run_update() -> None:
    local_ver = _read_local_version(MAIN_FOLDER)
    release = _github_latest_release()
    remote_tag = str(release.get("tag_name", "")).lstrip("v").strip() or "0.0.0"

    print(f"Local version:  {local_ver}")
    print(f"Remote version: {remote_tag}")

    if not _is_remote_newer(local_ver, remote_tag):
        print("Already up to date.")
        return

    asset_url = _pick_asset_url(release)
    if not asset_url:
        raise RuntimeError(
            f"Could not find '{ASSET_NAME}' asset or zipball in latest release."
        )

    print(f"Updating {local_ver} -> {remote_tag}")
    zip_bytes = _download(asset_url)

    backup_dir = _backup(MAIN_FOLDER)
    touched_files: list[Path] = []

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            _extract_zip_safely(zip_bytes, temp_path)
            src_root = _find_source_root(temp_path)
            touched_files = _copy_whitelisted(src_root, MAIN_FOLDER, backup_dir)
    except Exception:
        _restore_from_backup(MAIN_FOLDER, backup_dir, touched_files)
        raise

    print("Update applied.")
    print("Backup saved to: .backup_before_update")


def main() -> None:
    print("Welcome to the file checker, you can either")
    print("[1] - Run a file check (required files/folders exist)")
    print("[2] - Update from latest GitHub release (whitelisted paths only)")

    raw = input(">")
    try:
        answer = int(raw)
    except ValueError:
        print("Invalid input. Enter 1 or 2.")
        return

    if answer == 1:
        _run_file_check()
    elif answer == 2:
        confirm = input("Run updater now? [Y/N] > ").strip().lower()
        if confirm == "y":
            _run_update()
        else:
            print("Update canceled.")
    else:
        print("Invalid input. Enter 1 or 2.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Update failed: {exc}")
        sys.exit(1)
