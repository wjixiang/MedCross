"""基于 dict 的进程内内存缓存。"""

from __future__ import annotations

from typing import Any

from .base import ICache


class MemoryCache(ICache):
    """基于 dict 的进程内内存缓存。

    线程安全需外部加锁，本实现不内置锁以保持零依赖。
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Any | None:
        value = self._store.get(key)
        if value is not None:
            self._hits += 1
        else:
            self._misses += 1
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def info(self) -> dict[str, Any]:
        return {
            "type": "memory",
            "total_entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
        }
