"""队列领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CohortFilter(BaseModel):
    """队列筛选条件。"""

    biomarker_ranges: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="biomarker 字段 ID 到 (min, max) 范围的映射。",
    )
    limit: int = Field(default=100, ge=1, le=500000)
    offset: int = Field(default=0, ge=0)


class CohortInfo(BaseModel):
    """队列信息。"""

    id: str = Field(description="队列 ID。")
    name: str = ""
    size: int = Field(default=0, description="参与者数量。")
    filters: dict = Field(default_factory=dict, description="筛选条件。")
