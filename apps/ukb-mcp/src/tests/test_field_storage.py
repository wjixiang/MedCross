"""FieldStorageService 的测试。"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pandas as pd
import pytest

from ukb_mcp.service.fieldStorageService import FieldStorageService


@pytest.fixture
def db_path(tmp_path):
    """创建临时 DuckDB 文件，测试结束后自动清理。"""
    path = tmp_path / "test.duckdb"
    yield str(path)


@pytest.fixture
def mock_dx_client():
    """模拟 IDXClient。"""
    client = MagicMock()
    client.get_data_dictionary.return_value = pd.DataFrame(
        {
            "entity": ["participant", "participant", "participant"],
            "name": ["p36_i0", "p36_i1", "p36_i2"],
            "type": ["string", "string", "string"],
            "primary_key_type": ["", "", ""],
            "title": [
                "Blood pressure device ID | Instance 0",
                "Blood pressure device ID | Instance 1",
                "Blood pressure device ID | Instance 2",
            ],
            "description": ["None", "None", "None"],
            "coding_name": ["None", "None", "None"],
            "concept": ["None", "None", "None"],
            "folder_path": [
                "Assessment centre/Physical measures/Blood pressure device ID",
                "Assessment centre/Physical measures/Blood pressure device ID",
                "Assessment centre/Physical measures/Blood pressure device ID",
            ],
            "is_multi_select": [False, False, False],
            "is_sparse_coding": [False, False, False],
            "linkout": [
                "http://biobank.ctsu.ox.ac.uk/crystal/field.cgi?id=36",
                "http://biobank.ctsu.ox.ac.uk/crystal/field.cgi?id=36",
                "http://biobank.ctsu.ox.ac.uk/crystal/field.cgi?id=36",
            ],
            "longitudinal_axis_type": ["None", "None", "None"],
            "referenced_entity_field": ["", "", ""],
            "relationship": ["", "", ""],
            "units": [float("nan"), float("nan"), float("nan")],
        }
    )
    return client


@pytest.fixture
def service(db_path, mock_dx_client):
    """创建 FieldStorageService 实例。"""
    return FieldStorageService(db_path, mock_dx_client)


def test_sync_field_dict(service):
    service.sync_field_dict()
    df = service.list_fields()
    assert df.shape == (3, 16)


def test_sql_query(service):
    service.sync_field_dict()
    result = service.query_fields("TRUE")
    print(result)
