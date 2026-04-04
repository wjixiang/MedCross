"""数据库领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatabaseInfo(BaseModel):
    """数据库基本信息。"""

    id: str
    name: str = ""
    state: str = ""
    project: str = ""
    created: int = 0
    modified: int = 0


class DatabaseTableInfo(BaseModel):
    """数据库中的数据表。"""

    name: str


class DatabaseFieldListRequest(BaseModel):
    """字段列表查询请求。"""

    entity: str | None = Field(default=None, description="按实体过滤，如 participant。")
    name_pattern: str | None = Field(default=None, description="按字段名模糊匹配。")
    refresh: bool = Field(default=False, description="为 True 时跳过缓存，强制从云端获取。")


class DatabaseQueryRequest(BaseModel):
    """数据库查询请求。"""

    entity_fields: list[str] = Field(
        default_factory=list,
        description='"entity.field_name" 格式的字段列表。',
    )
    dataset_ref: str | None = Field(default=None, description="数据集引用，为空则自动查找。")
    refresh: bool = Field(default=False, description="为 True 时跳过缓存，强制从云端获取。")


class DatabaseExportRequest(BaseModel):
    """数据库导出请求。"""

    entity_fields: list[str] = Field(
        default_factory=list,
        description='"entity.field_name" 格式的字段列表。',
    )
    dataset_ref: str | None = Field(default=None, description="数据集引用，为空则自动查找。")
    refresh: bool = Field(default=False, description="为 True 时跳过缓存，强制从云端获取。")
