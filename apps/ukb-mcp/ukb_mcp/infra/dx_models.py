"""DNAnexus 平台 Pydantic 数据模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DXClientConfig(BaseModel):
    """DXClient 连接配置。

    优先级：构造参数 > 环境变量 > 默认值。
    """

    auth_token: str = Field(
        default="",
        description="DNAnexus auth token，对应环境变量 DX_AUTH_TOKEN。",
    )
    project_context_id: str = Field(
        default="",
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
