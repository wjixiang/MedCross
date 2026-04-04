"""生物标志物领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BiomarkerField(BaseModel):
    """单个 biomarker 字段。"""

    field_id: str = Field(description="UKB 字段 ID，如 30030。")
    name: str = Field(description="字段名称，如 Cholesterol。")
    category: str = Field(default="", description="分类，如 participant。")
    type: str = Field(default="", description="字段类型，如 Integer / Continuous。")


class BiomarkerStats(BaseModel):
    """单个 biomarker 字段的统计摘要。"""

    field_id: str = Field(description="字段 ID。")
    name: str = Field(default="", description="字段名称。")
    count: int = Field(default=0, description="非缺失值数量。")
    mean: float | None = Field(default=None, description="均值。")
    std: float | None = Field(default=None, description="标准差。")
    min: float | None = Field(default=None, description="最小值。")
    max: float | None = Field(default=None, description="最大值。")
    median: float | None = Field(default=None, description="中位数。")
    missing_rate: float | None = Field(default=None, description="缺失比例 0~1。")


class BiomarkerQuery(BaseModel):
    """biomarker 查询请求。"""

    fields: list[str] = Field(default_factory=list, description="字段 ID 列表。")
    limit: int = Field(default=100, ge=1, le=10000, description="返回行数上限。")
    offset: int = Field(default=0, ge=0, description="行偏移量。")
    refresh: bool = Field(default=False, description="强制刷新缓存。")
