"""数据导出业务逻辑。"""

from __future__ import annotations

import logging

import pandas as pd
from dx_client import IDXClient

logger = logging.getLogger(__name__)


class ExportService:
    """数据导出服务。"""

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    def query(
        self, fields: list[str], cohort_id: str = "", *, refresh: bool = False,
    ) -> pd.DataFrame:
        if not fields:
            raise ValueError("fields must not be empty")

        db = self._dx.find_database(refresh=refresh)
        return self._dx.query_database(db.id, fields, refresh=refresh)
