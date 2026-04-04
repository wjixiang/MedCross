"""基于 DuckDB 的持久化缓存。

将缓存数据持久化到本地 DuckDB 文件，进程重启后缓存仍然有效。
适合数据字典等获取成本高、变化频率低的场景。

需要安装可选依赖：``pip install duckdb``
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any

from .base import ICache

logger = logging.getLogger(__name__)


class DuckDBCache(ICache):
    """基于 DuckDB 的持久化缓存。

    使用 pickle 序列化 Python 对象，存储在单表 DuckDB 数据库中。

    Args:
        db_path: DuckDB 数据库文件路径。为 ``:memory:`` 时退化为内存模式。
                 默认 ``.cache/dx_cache.duckdb``。
    """

    def __init__(self, db_path: str | Path = ".cache/dx_cache.duckdb") -> None:
        super().__init__()
        self._db_path = str(db_path)
        self._hits: int = 0
        self._misses: int = 0
        self._initialized = False
        self._ensure_db()

    def _ensure_db(self) -> None:
        try:
            import duckdb
        except ImportError:
            raise ImportError(
                "duckdb is required for DuckDBCache. "
                "Install it with: pip install duckdb"
            )

        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self._db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_store (
                key   VARCHAR PRIMARY KEY,
                value BLOB,
                ts    TIMESTAMP DEFAULT current_timestamp
            )
            """
        )
        self._initialized = True

    def _inner_get(self, key: str) -> Any | None:
        if not self._initialized:
            return None
        try:
            row = self._conn.execute(
                "SELECT value FROM cache_store WHERE key = ?", [key]
            ).fetchone()
            if row is not None:
                return pickle.loads(row[0])
            return None
        except Exception:
            logger.warning("DuckDBCache.get failed for key=%s", key, exc_info=True)
            return None

    def set(self, key: str, value: Any) -> None:
        if not self._initialized:
            return
        try:
            blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            self._conn.execute(
                """
                INSERT INTO cache_store (key, value, ts) VALUES (?, ?, current_timestamp)
                ON CONFLICT (key) DO UPDATE SET value = excluded.value, ts = excluded.ts
                """,
                [key, blob],
            )
        except Exception:
            logger.warning("DuckDBCache.set failed for key=%s", key, exc_info=True)

    def delete(self, key: str) -> None:
        if not self._initialized:
            return
        try:
            self._conn.execute("DELETE FROM cache_store WHERE key = ?", [key])
        except Exception:
            logger.warning("DuckDBCache.delete failed for key=%s", key, exc_info=True)

    def clear(self) -> None:
        if not self._initialized:
            return
        try:
            self._conn.execute("DELETE FROM cache_store")
            self._hits = 0
            self._misses = 0
        except Exception:
            logger.warning("DuckDBCache.clear failed", exc_info=True)

    def info(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "duckdb",
            "db_path": self._db_path,
            "hits": self._hits,
            "misses": self._misses,
        }
        if self._initialized:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM cache_store"
                ).fetchone()
                result["total_entries"] = row[0]
            except Exception:
                result["total_entries"] = -1
        return result

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._initialized:
            try:
                self._conn.close()
            except Exception:
                pass
            self._initialized = False
