"""生物标志物领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BiomarkerField(BaseModel):
    """单个 biomarker 字段描述。"""

    field_id: str = Field(description="UKB 字段 ID，如 30030。")
    name: str = Field(description="字段名称，如 Cholesterol。")
    category: str = Field(default="", description="分类，如 Biochemistry。")
    description: str = Field(default="", description="字段描述。")


class BiomarkerStats(BaseModel):
    """单个 biomarker 字段的统计摘要。"""

    field_id: str
    name: str = ""
    count: int = Field(default=0, description="非缺失值数量。")
    mean: float | None = Field(default=None)
    std: float | None = Field(default=None)
    min: float | None = Field(default=None)
    max: float | None = Field(default=None)
    median: float | None = Field(default=None)
    missing_rate: float | None = Field(default=None, description="缺失比例 0~1。")


class BiomarkerQuery(BaseModel):
    """biomarker 查询请求。"""

    fields: list[str] = Field(default_factory=list, description="字段 ID 列表。")
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
