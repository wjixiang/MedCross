"""队列领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CohortFilter(BaseModel):
    """队列筛选条件。"""

    biomarker_ranges: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="biomarker 字段 ID 到 (min, max) 范围的映射。",
    )
    limit: int = Field(default=100, ge=1, le=500000)
    offset: int = Field(default=0, ge=0)


class CohortCreateRequest(BaseModel):
    """创建队列请求。"""

    name: str = Field(description="队列名称。")
    participant_ids: list[str] | None = Field(
        default=None,
        description="参与者 ID 列表。与 filters 二选一。",
    )
    filters: dict | None = Field(
        default=None,
        description="原始 vizserver pheno_filters 结构。与 participant_ids 二选一。",
    )
    dataset_ref: str | None = Field(default=None, description="Dataset 引用。")
    folder: str = Field(default="/", description="目标文件夹路径。")
    description: str = Field(default="", description="队列描述。")
    validate_ids: bool = Field(default=True, description="是否校验 ID 存在于 dataset。")
    entity_fields: list[str] = Field(
        default_factory=list,
        description='关联字段列表（"entity.field_name" 格式）。',
    )

    @model_validator(mode="after")
    def check_cohort_definition(self) -> "CohortCreateRequest":
        if self.participant_ids is not None and self.filters is not None:
            raise ValueError(
                "Provide exactly one of 'participant_ids' or 'filters', not both."
            )
        if self.participant_ids is None and self.filters is None:
            raise ValueError(
                "Either 'participant_ids' or 'filters' must be provided."
            )
        return self


class CohortInfo(BaseModel):
    """队列信息（创建接口返回）。"""

    id: str = Field(description="队列 ID。")
    name: str = ""
    project: str = ""
    folder: str = ""
    state: str = ""
    description: str = ""
    created: int = 0
    modified: int = 0
    participant_count: int = Field(default=0, description="参与者数量。")
    entity_fields: list[str] = Field(default_factory=list, description="关联字段。")


class CohortListItem(BaseModel):
    """队列列表项。"""

    id: str = Field(description="队列 record ID。")
    name: str = ""
    project: str = ""
    state: str = ""
    created: int = 0
    modified: int = 0


class CohortDetail(BaseModel):
    """队列详情（含 record details）。"""

    id: str = Field(description="队列 record ID。")
    name: str = ""
    project: str = ""
    state: str = ""
    created: int = 0
    modified: int = 0
    details: dict = Field(default_factory=dict, description="record details。")


class ExtractFieldsRequest(BaseModel):
    """提取字段请求。"""

    entity_fields: list[str] = Field(description='要提取的字段列表（"entity.field_name" 格式）。')
    refresh: bool = Field(default=False, description="是否跳过缓存。")
