"""关联查询业务逻辑。"""

from __future__ import annotations

from dx_client import IDXClient


class AssociationService:
    """关联查询服务。"""

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    def query(self, biomarker_id: str, outcome_id: str = "", limit: int = 100) -> list[dict]:
        """查询 biomarker 与结局的关联。"""
        raise NotImplementedError
