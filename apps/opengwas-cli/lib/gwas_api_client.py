"""OpenGWAS API 客户端封装。

提供统一的客户端获取逻辑，将 API 返回的原始 JSON 转换为 pandas DataFrame。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from gwas_client import OpenGWAS_API_Client

# 从项目根目录向上搜索 .env，同时检查 libs/gwas-client/.env
_workspace_root = Path(__file__).resolve().parents[3]  # apps/opengwas-cli/lib -> project root
for env_path in [
    _workspace_root / ".env",
    _workspace_root / "libs" / "gwas-client" / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        break


def _to_df(data: Any) -> pd.DataFrame:
    """将 API 返回的原始数据转换为 DataFrame。

    支持的格式：
    - list[dict]: 直接转为 DataFrame；自动展平 Elasticsearch 风格的 {_id, _source} 结构
    - dict[str, dict]: dict-of-dicts（如 gwasinfo），每个 value 变为一行
    - dict[str, list]: dict-of-lists（分页结构），取第一个 list
    - dict: 单条记录
    """
    if isinstance(data, list):
        # list[str]: 转为单列 DataFrame
        if data and isinstance(data[0], str):
            return pd.DataFrame(data, columns=["rsid"])
        df = pd.DataFrame(data)
        # 展平 Elasticsearch 风格: {_id, _source: {field: value}}
        if "_source" in df.columns and "_id" in df.columns:
            flat = pd.json_normalize(df["_source"].tolist())
            flat.insert(0, "rsid", df["_id"].values)
            return flat
        return df
    if isinstance(data, dict):
        if data and all(isinstance(v, dict) for v in data.values()):
            df = pd.DataFrame.from_dict(data, orient="index")
            if "id" not in df.columns:
                df.index.name = "id"
                df = df.reset_index()
            return df
        for v in data.values():
            if isinstance(v, list) and len(v) > 0:
                # dict[str, list[str]]: 如 gwasinfo/files 返回 {id: [url1, url2]}
                if isinstance(v[0], str):
                    rows = [(k, url) for k, urls in data.items() if isinstance(urls, list) for url in urls]
                    return pd.DataFrame(rows, columns=["id", "url"])
                return pd.DataFrame(v)
        return pd.DataFrame([data])
    return pd.DataFrame()


def get_client(token: str | None = None) -> OpenGWAS_API_Client:
    """获取已认证的 API 客户端。

    Token 优先级：参数 token > OPENGWAS_TOKEN 环境变量 > .env 中的 IEU_TOKEN。
    """
    resolved = token or os.environ.get("OPENGWAS_TOKEN") or os.environ.get("IEU_TOKEN")
    return OpenGWAS_API_Client(token=resolved)
