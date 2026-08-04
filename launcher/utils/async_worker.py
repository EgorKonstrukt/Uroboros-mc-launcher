import sys
import time
import threading
import traceback
from typing import Callable, Optional, Any

from PyQt6.QtCore import QObject, pyqtSignal


class ErrorInfo:
    def __init__(self, message: str, traceback_text: str = ""):
        self.message = message
        self.traceback = traceback_text

    def __str__(self) -> str:
        return self.message


def _log_error(tb: str):
    try:
        from launcher.utils.storage import get_logs_dir
        logs = get_logs_dir()
        logs.mkdir(parents=True, exist_ok=True)
        path = logs / "launcher.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {tb}\n")
    except Exception:
        pass


class _Signals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(object)


def _make_slot(callback, signal):
    def slot(value):
        callback(value)
    return slot


def run_async(
    fn: Callable[[], Any],
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> threading.Thread:
    invoker = _Signals()
    slot_done = _make_slot(on_done, invoker.done) if on_done else None
    slot_error = _make_slot(on_error, invoker.error) if on_error else None

    if slot_done:
        invoker.done.connect(slot_done)
    if slot_error:
        invoker.error.connect(slot_error)

    def wrapper():
        try:
            result = fn()
            if slot_done:
                invoker.done.emit(result)
        except Exception as e:
            tb = traceback.format_exc()
            _log_error(tb)
            if slot_error:
                invoker.error.emit(ErrorInfo(str(e), tb))
            elif sys.stderr is not None:
                sys.stderr.write(tb)

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t


def run_async_callback(fn, callback, *args, **kwargs):
    return run_async(fn, on_done=callback, *args, **kwargs)
