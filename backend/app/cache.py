"""Cache hasil analisis graf dalam memori; dibatalkan setiap kali data berubah."""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Callable

_lock = threading.Lock()
_version = 0
_store: "OrderedDict[tuple, Any]" = OrderedDict()
_MAX = 64


def bump() -> None:
    global _version
    with _lock:
        _version += 1
        _store.clear()


def cached(key: tuple, fn: Callable[[], Any]) -> Any:
    k = (_version, *key)
    with _lock:
        if k in _store:
            _store.move_to_end(k)
            return _store[k]
    val = fn()
    with _lock:
        _store[k] = val
        while len(_store) > _MAX:
            _store.popitem(last=False)
    return val
