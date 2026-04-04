"""缓存模块 — 提供可插拔的缓存策略。"""

from .base import ICache
from .memory import MemoryCache

__all__ = ["ICache", "MemoryCache", "DuckDBCache"]


def __getattr__(name: str):
    if name == "DuckDBCache":
        from .duckdb_cache import DuckDBCache

        return DuckDBCache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
