"""DXClient 自定义异常层级。"""


from __future__ import annotations


class DXClientError(Exception):
    """DXClient 基础异常。"""

    def __init__(self, message: str, *, dx_error: Exception | None = None) -> None:
        self.dx_error = dx_error
        super().__init__(message)


class DXAuthError(DXClientError):
    """认证失败（无效或缺失 token）。"""


class DXProjectNotFoundError(DXClientError):
    """项目不存在或无权访问。"""


class DXFileNotFoundError(DXClientError):
    """文件不存在。"""


class DXAPIError(DXClientError):
    """DNAnexus API 调用失败。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        error_type: str = "",
        dx_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message, dx_error=dx_error)


class DXConfigError(DXClientError):
    """客户端配置无效。"""
