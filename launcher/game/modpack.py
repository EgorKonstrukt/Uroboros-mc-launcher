import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

import requests

from launcher.utils.progress import ParallelProgress, CancelledError

CHUNK = 262144
WORKERS = 24


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def download_modpack_files(
    files: list,
    mp_dir: Path,
    open_file: Callable,
    progress_callback: Callable = None,
    should_cancel: Callable = None,
) -> bool:
    total = len(files)
    if total == 0:
        return True
    progress = ParallelProgress(progress_callback, "modpack", total)
    workers = max(1, min(WORKERS, total))

    def attempt(name, expected, tmp, dest):
        resp = None
        try:
            resp = open_file(name)
        except requests.RequestException:
            return False
        try:
            if resp.status_code != 200:
                return False
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK):
                    if not chunk:
                        continue
                    f.write(chunk)
                    progress.tick(name, len(chunk))
                    if should_cancel and should_cancel():
                        raise CancelledError()
            if expected and _sha256(tmp) != expected:
                return False
            tmp.replace(dest)
            return True
        finally:
            resp.close()

    def work(f):
        name = f["name"]
        expected = f.get("sha256", "") or ""
        size = f.get("size", 0)
        dest = mp_dir / name
        if dest.exists() and dest.is_file():
            if expected:
                if _sha256(dest) == expected:
                    progress.finish(name)
                    return True
            elif size and dest.stat().st_size == size:
                progress.finish(name)
                return True
        if should_cancel and should_cancel():
            raise CancelledError()
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        try:
            progress.start_file(name)
            ok = False
            for i in range(3):
                if i:
                    time.sleep(1.0)
                ok = attempt(name, expected, tmp, dest)
                if ok or (should_cancel and should_cancel()):
                    break
            return ok
        except CancelledError:
            raise
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            progress.finish(name)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(work, files))
    return all(results)
