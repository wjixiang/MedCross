"""关联查询领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssociationQuery(BaseModel):
    """关联查询请求。"""

    biomarker_id: str = Field(description="biomarker 字段 ID。")
    outcome_id: str = Field(default="", description="结局字段/ICD 编码。")
    limit: int = Field(default=100, ge=1, le=10000)


class AssociationResult(BaseModel):
    """关联查询结果。"""

    biomarker_id: str
    outcome_id: str = ""
    p_value: float | None = None
    beta: float | None = None
    se: float | None = None
    or_value: float | None = Field(default=None, description="Odds Ratio。")
    ci_lower: float | None = Field(default=None, description="95% CI 下限。")
    ci_upper: float | None = Field(default=None, description="95% CI 上限。")
