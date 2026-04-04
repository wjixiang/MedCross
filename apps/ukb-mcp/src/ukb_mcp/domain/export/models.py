"""数据导出领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    """数据导出请求。"""

    fields: list[str] = Field(
        default_factory=list,
        description="导出字段 ID 列表。",
    )
    cohort_id: str = Field(
        default="",
        description="队列 ID，为空则导出全量。",
    )
    refresh: bool = Field(default=False, description="强制刷新缓存。")
