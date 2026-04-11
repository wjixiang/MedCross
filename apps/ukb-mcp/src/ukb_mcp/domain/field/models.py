"""字段字典领域模型。"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, model_validator


class FieldDictItem(BaseModel):
    """字段字典单条记录。"""

    entity: str
    name: str
    type: str
    primary_key_type: str | None = None
    title: str | None = None
    description: str | None = None
    coding_name: str | None = None
    concept: str | None = None
    folder_path: str | None = None
    is_multi_select: bool | None = False
    is_sparse_coding: bool | None = False
    linkout: str | None = None
    longitudinal_axis_type: str | None = None
    referenced_entity_field: str | None = None
    relationship: str | None = None
    units: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _nan_to_none(cls, values: object) -> object:
        if isinstance(values, dict):
            for k, v in values.items():
                if isinstance(v, float) and math.isnan(v):
                    values[k] = None
        return values


class FieldDictResponse(BaseModel):
    """字段字典查询响应。"""

    total: int = Field(description="总记录数。")
    page: int = Field(description="当前页码。")
    page_size: int = Field(description="每页条数。")
    data: list[FieldDictItem] = Field(description="字段列表。")
