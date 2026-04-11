from __future__ import annotations

import duckdb
from fastapi import Depends

from dx_client import IDXClient
from ukb_mcp.api.deps import get_dx_client
from ukb_mcp.config import get_settings
import sqlglot


def get_field_storage(
    dx_client: IDXClient = Depends(get_dx_client),
) -> FieldStorageService:
    settings = get_settings()
    return FieldStorageService(settings.db_path, dx_client)


class FieldStorageService:
    def __init__(self, db_path: str, dx_client: IDXClient) -> None:
        self._con = duckdb.connect(db_path)
        self._dx = dx_client

    def sync_field_dict(self):
        df = self._dx.get_data_dictionary(refresh=False)
        self._con.register("tmp", df)
        self._con.execute("DROP TABLE IF EXISTS field_dict")
        self._con.execute("CREATE TABLE field_dict AS SELECT * FROM tmp")
        self._con.unregister("tmp")
        return True

    def list_fields(self, page: int = 1, page_size: int = 100):
        offset = (page - 1) * page_size
        return self._con.execute(
            "SELECT * FROM field_dict LIMIT ? OFFSET ?",
            [page_size, offset],
        ).df()

    def query_fields(self, condition: str, page: int = 1, page_size: int = 100):
        offset = (page - 1) * page_size
        parsed = sqlglot.parse_one(condition, dialect="duckdb")

        query = (
            sqlglot.select("*")
            .from_("field_dict")
            .where(parsed)
            .limit(page_size)
            .offset(offset)
        )

        return self._con.execute(query.sql(dialect="duckdb")).df()
