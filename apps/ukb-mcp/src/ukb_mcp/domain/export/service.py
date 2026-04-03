"""数据导出业务逻辑。"""

from __future__ import annotations

from pathlib import Path

from ukb_mcp.infra import IDXClient


class ExportService:
    """数据导出服务。"""

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    def to_csv(self, fields: list[str], cohort_id: str = "") -> Path:
        """导出为 CSV 文件。"""
        raise NotImplementedError

    def to_parquet(self, fields: list[str], cohort_id: str = "") -> Path:
        """导出为 Parquet 文件。"""
        raise NotImplementedError
