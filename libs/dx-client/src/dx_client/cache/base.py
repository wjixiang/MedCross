"""缓存抽象接口。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CacheStatus(str, Enum):
    """缓存操作结果。"""

    HIT = "hit"
    MISS = "miss"
    SKIP = "skip"  # refresh=True 跳过缓存


class ICache(ABC):
    """数据缓存抽象接口。

    提供通用的 get/set/clear 语义，与业务逻辑解耦。
    任何实现（内存、DuckDB、Redis 等）均可通过依赖注入接入。
    """

    def __init__(self) -> None:
        self.last_status: CacheStatus = CacheStatus.MISS

    @abstractmethod
    def _inner_get(self, key: str) -> Any | None:
        """子类实现的实际读取逻辑。"""

    def get(self, key: str) -> Any | None:
        """读取缓存，命中时记录 INFO 日志。"""
        value = self._inner_get(key)
        if value is not None:
            self.last_status = CacheStatus.HIT
            logger.info("cache hit  [%s]", key)
        else:
            self.last_status = CacheStatus.MISS
            logger.info("cache miss [%s]", key)
        return value

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """写入缓存。"""

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除指定缓存键，不存在时静默跳过。"""

    @abstractmethod
    def clear(self) -> None:
        """清除全部缓存。"""

    @abstractmethod
    def info(self) -> dict[str, Any]:
        """返回缓存统计信息。"""
