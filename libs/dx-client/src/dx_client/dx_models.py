"""DNAnexus 平台 Pydantic 数据模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings


class DXClientConfig(BaseSettings):
    """DXClient 连接配置。

    优先级：构造参数 > 环境变量 > 默认值。
    """

    model_config = ConfigDict(env_prefix="", extra="ignore")

    auth_token: str = Field(
        default="",
        validation_alias="DX_AUTH_TOKEN",
        description="DNAnexus auth token，对应环境变量 DX_AUTH_TOKEN。",
    )
    project_context_id: str = Field(
        default="",
        validation_alias="DX_PROJECT_CONTEXT_ID",
        description="默认项目上下文 ID，对应环境变量 DX_PROJECT_CONTEXT_ID。",
    )
    api_server_host: str = Field(
        default="api.dnanexus.com",
        description="DNAnexus API 服务器主机名。",
    )
    api_server_port: int = Field(
        default=443,
        description="DNAnexus API 服务器端口。",
    )
    api_server_protocol: str = Field(
        default="https",
        description="DNAnexus API 协议 (http / https)。",
    )


class DXProject(BaseModel):
    """DNAnexus 项目描述。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    description: str = ""
    created: int = 0
    modified: int = 0
    data_usage: dict[str, Any] = Field(default_factory=dict)
    region: str = ""
    total_size: int = 0
    billable: bool = True
    permission_level: str = ""


class DXFileInfo(BaseModel):
    """DNAnexus 文件元数据。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    project: str = ""
    folder: str = ""
    state: str = ""
    size: int = 0
    created: int = 0
    modified: int = 0
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    md5: str = ""
    sha256: str = ""


class DXRecordInfo(BaseModel):
    """DNAnexus 记录元数据。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    project: str = ""
    folder: str = ""
    created: int = 0
    modified: int = 0
    state: str = ""
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    types: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class DXDatabaseInfo(BaseModel):
    """DNAnexus database 数据对象描述。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    project: str = ""
    name: str = ""
    folder: str = ""
    state: str = ""
    created: int = 0
    modified: int = 0
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "visible"
    database_name: str = ""
    db_schema: dict[str, Any] = Field(default_factory=dict, alias="schema")
    record_count: int = 0


class DXDatabaseColumn(BaseModel):
    """数据库列描述。"""

    model_config = ConfigDict(extra="allow")

    name: str = ""
    type: str = ""
    description: str = ""
    nullable: bool = True


class DXDatabaseTable(BaseModel):
    """数据库表描述，包含所有列信息。"""

    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    columns: list[DXDatabaseColumn] = Field(default_factory=list)


class DXDataObject(BaseModel):
    """DNAnexus 通用数据对象描述。"""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    project: str = ""
    name: str = ""
    folder: str = ""
    classname: str = ""
    state: str = ""
    created: int = 0
    modified: int = 0
    size: int = 0
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)


class DXCohortInfo(BaseModel):
    """DNAnexus cohort record 描述。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = ""
    name: str = ""
    project: str = ""
    folder: str = ""
    state: str = ""
    description: str = ""
    created: int = 0
    modified: int = 0
    participant_count: int = 0
    entity_fields: list[str] = Field(default_factory=list)


class DXDatabaseClusterInfo(BaseModel):
    """DNAnexus database 对象完整描述（来自 database_describe API）。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = ""
    project: str = ""
    name: str = ""
    class_name: str = Field(default="", alias="class")
    state: str = ""
    created: int = 0
    modified: int = 0
    folder: str = ""
    description: str = ""
    database_name: str = Field(default="", alias="databaseName")
    unique_database_name: str = Field(default="", alias="uniqueDatabaseName")
    visibility: str = "visible"
    sponsored: bool = False
    hidden: bool = False


class DXJobInfo(BaseModel):
    """DNAnexus job 描述。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = ""
    name: str = ""
    state: str = ""
    project: str = ""
    folder: str = ""
    created: int = 0
    modified: int = 0
    started_running: int = Field(default=0, alias="startedRunning")
    stopped_running: int = Field(default=0, alias="stoppedRunning")
    executable_name: str = Field(default="", alias="executableName")
    launched_by: str = Field(default="", alias="launchedBy")
    root_execution: str = Field(default="", alias="rootExecution")
    parent_job: str = Field(default="", alias="parentJob")
    origin_job: str = Field(default="", alias="originJob")
    function: str = ""
    region: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    run_input: dict[str, Any] = Field(default_factory=dict, alias="runInput")
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str = Field(default="", alias="failureReason")
    failure_message: str = Field(default="", alias="failureMessage")
    state_transitions: list[dict[str, Any]] = Field(
        default_factory=list, alias="stateTransitions",
    )
    app: str = ""
    applet: str = ""
    analysis: str = ""
    bill_to: str = Field(default="", alias="billTo")
    total_price: float = Field(default=0.0, alias="totalPrice")
