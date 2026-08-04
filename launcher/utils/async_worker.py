import sys
import threading
import traceback
from typing import Callable, Optional, Any

from PyQt6.QtCore import QObject, pyqtSignal


class _Signals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(str)


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
            if slot_error:
                invoker.error.emit(str(e))
            elif sys.stderr is not None:
                traceback.print_exc()

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t


def run_async_callback(fn, callback, *args, **kwargs):
    return run_async(fn, on_done=callback, *args, **kwargs)
