"""生物标志物业务逻辑。"""

from __future__ import annotations

from ukb_mcp.infra import IDXClient


class BiomarkerService:
    """生物标志物查询服务。"""

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    def list_fields(self) -> list[dict]:
        """列出可用的 biomarker 字段。"""
        raise NotImplementedError

    def get_stats(self, field_id: str) -> dict:
        """获取字段统计摘要。"""
        raise NotImplementedError

    def query(self, fields: list[str], limit: int = 100, offset: int = 0) -> list[dict]:
        """查询指定字段的值。"""
        raise NotImplementedError
