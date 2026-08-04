import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from launcher.utils.progress import CancelledError

CHUNK = 262144
MIN_PARALLEL_SIZE = 8 * 1024 * 1024
DEFAULT_PARTS = 4
MAX_PARTS = 8


def _probe(session, url: str, timeout: int):
    resp = session.get(url, headers={"Range": "bytes=0-0"}, timeout=timeout, stream=True)
    try:
        if resp.status_code != 206:
            return False, 0
        cr = resp.headers.get("content-range", "")
        if not cr:
            return False, 0
        try:
            total = int(cr.rsplit("/", 1)[1])
        except (ValueError, IndexError):
            total = 0
        return total > 0, total
    finally:
        resp.close()


def _parts_for(total: int, parts: int) -> list:
    n = max(1, min(parts, MAX_PARTS))
    step = total // n
    ranges = []
    start = 0
    for i in range(n):
        end = total - 1 if i == n - 1 else start + step - 1
        ranges.append((start, end))
        start = end + 1
    return ranges


def _download_part(session, url: str, start: int, end: int, tmp: Path,
                   on_bytes: Callable, should_cancel: Callable, timeout: int) -> bool:
    resp = session.get(
        url, headers={"Range": f"bytes={start}-{end}"}, timeout=timeout, stream=True
    )
    try:
        if resp.status_code != 206:
            return False
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK):
                if not chunk:
                    continue
                f.write(chunk)
                on_bytes(len(chunk))
                if should_cancel and should_cancel():
                    raise CancelledError()
        return True
    finally:
        resp.close()


def download_parallel(
    session,
    url: str,
    dest: Path,
    on_total: Callable[[int], None] = None,
    on_bytes: Callable[[int], None] = None,
    should_cancel: Callable = None,
    parts: int = DEFAULT_PARTS,
    min_size: int = MIN_PARALLEL_SIZE,
    timeout: int = 300,
) -> bool:
    on_total = on_total or (lambda t: None)
    on_bytes = on_bytes or (lambda n: None)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")

    supported, total = _probe(session, url, timeout)
    if not supported or total < min_size:
        resp = session.get(url, timeout=timeout, stream=True)
        try:
            if resp.status_code != 200:
                raise IOError(f"Download failed with HTTP {resp.status_code}")
            on_total(int(resp.headers.get("content-length", 0) or 0))
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK):
                    if not chunk:
                        continue
                    f.write(chunk)
                    on_bytes(len(chunk))
                    if should_cancel and should_cancel():
                        raise CancelledError()
        finally:
            resp.close()
        tmp.replace(dest)
        return True

    ranges = _parts_for(total, parts)
    part_files = [dest.with_name(f"{dest.name}.part{i}") for i in range(len(ranges))]
    try:
        on_total(total)
        with ThreadPoolExecutor(max_workers=len(ranges)) as executor:
            futures = [
                executor.submit(_download_part, session, url, s, e, part_files[i],
                                on_bytes, should_cancel, timeout)
                for i, (s, e) in enumerate(ranges)
            ]
            for f in futures:
                if not f.result():
                    raise IOError("Failed to download a file chunk")
        with open(tmp, "wb") as out:
            for pf in part_files:
                with open(pf, "rb") as f:
                    shutil.copyfileobj(f, out, CHUNK)
        tmp.replace(dest)
        return True
    finally:
        for pf in part_files:
            try:
                if pf.exists():
                    pf.unlink()
            except OSError:
                pass
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
