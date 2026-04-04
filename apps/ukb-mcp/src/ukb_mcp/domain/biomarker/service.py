"""生物标志物业务逻辑。"""

from __future__ import annotations

import logging
from typing import cast

import pandas as pd
from dx_client import IDXClient

logger = logging.getLogger(__name__)


class BiomarkerService:
    """生物标志物查询服务。

    通过 ``IDXClient`` 抽象接口访问 UKB-RAP 数据集，
    不直接依赖 dxpy SDK 或 dx CLI。
    """

    def __init__(self, dx_client: IDXClient) -> None:
        self._dx = dx_client

    # ── 内部辅助 ──────────────────────────────────────────────────────────

    def _resolve_field_name(self, data_dict: pd.DataFrame, field_id: str) -> tuple[str, str]:
        """从 data_dictionary 中查找 field_id 对应的 DX field name 和 entity。

        Returns:
            (field_name, entity) 元组，例如 ("p21022", "participant")。
        """
        name_col = "name" if "name" in data_dict.columns else data_dict.columns[1]
        entity_col = "entity" if "entity" in data_dict.columns else data_dict.columns[0]

        for _, row in data_dict.iterrows():
            name = str(row[name_col])
            candidate_id = name.lstrip("p").split("_")[0]
            if candidate_id == field_id:
                return name, str(row[entity_col])

        raise ValueError(f"Field ID '{field_id}' not found in data dictionary")

    # ── 公共方法 ──────────────────────────────────────────────────────────

    def list_fields(
        self,
        entity: str | None = None,
        name_pattern: str | None = None,
        *,
        refresh: bool = False,
    ) -> list[dict]:
        df = self._dx.list_fields(
            entity=entity, name_pattern=name_pattern, refresh=refresh,
        )

        result: list[dict] = []
        for _, row in df.iterrows():
            name = str(row["name"])
            field_id = name.lstrip("p").split("_")[0] if name.startswith("p") else name
            result.append({
                "field_id": field_id,
                "name": str(row["title"]),
                "category": str(row["entity"]),
                "type": str(row["type"]),
            })
        return result

    def get_stats(self, field_id: str, *, refresh: bool = False) -> dict:
        data_dict = self._dx.get_data_dictionary(refresh=refresh)
        field_name, entity = self._resolve_field_name(data_dict, field_id)

        df = self._dx.extract_fields([f"{entity}.{field_name}"], refresh=refresh)
        if df.empty:
            return {"field_id": field_id, "name": field_name, "count": 0}

        col = df.columns[-1]
        s = cast(pd.Series, pd.to_numeric(df[col], errors="coerce"))
        count = int(s.notna().sum())
        total = len(s)

        return {
            "field_id": field_id,
            "name": field_name,
            "count": count,
            "mean": float(cast(float, s.mean())) if count > 0 else None,
            "std": float(cast(float, s.std())) if count > 0 else None,
            "min": float(cast(float, s.min())) if count > 0 else None,
            "max": float(cast(float, s.max())) if count > 0 else None,
            "median": float(cast(float, s.median())) if count > 0 else None,
            "missing_rate": round(1 - count / total, 4) if total > 0 else None,
        }

    def query(
        self, fields: list[str], limit: int = 100, offset: int = 0,
        *, refresh: bool = False,
    ) -> list[dict]:
        if not fields:
            return []

        data_dict = self._dx.get_data_dictionary(refresh=refresh)

        entity_fields: dict[str, list[str]] = {}
        for fid in fields:
            try:
                field_name, entity = self._resolve_field_name(data_dict, fid)
            except ValueError:
                logger.warning("Field ID '%s' not found, skipping", fid)
                continue
            entity_fields.setdefault(entity, []).append(field_name)

        if not entity_fields:
            return []

        entity = next(iter(entity_fields))
        field_names = entity_fields[entity]
        fields_arg = [f"{entity}.{f}" for f in field_names]

        df = self._dx.extract_fields(fields_arg, refresh=refresh)
        if df.empty:
            return []

        data_cols = [c for c in df.columns if c != "eid"]
        sliced = df[data_cols].iloc[offset : offset + limit]
        return sliced.to_dict(orient="records")
