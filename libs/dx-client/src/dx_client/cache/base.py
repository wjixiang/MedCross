"""缓存抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ICache(ABC):
    """数据缓存抽象接口。

    提供通用的 get/set/clear 语义，与业务逻辑解耦。
    任何实现（内存、DuckDB、Redis 等）均可通过依赖注入接入。
    """

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """读取缓存。命中返回值，未命中返回 None。"""

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
