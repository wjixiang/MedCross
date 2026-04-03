"""队列构建业务逻辑。"""

from __future__ import annotations

from ukb_mcp.infra import IDXClient


class CohortService:
    """队列构建服务。"""

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    def filter(self, filters: dict, limit: int = 100, offset: int = 0) -> list[dict]:
        """按条件筛选参与者。"""
        raise NotImplementedError

    def get_info(self, cohort_id: str) -> dict:
        """获取队列详情。"""
        raise NotImplementedError
