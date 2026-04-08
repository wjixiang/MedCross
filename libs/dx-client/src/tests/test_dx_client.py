"""DXClient 全方法可用性测试脚本。

通过项目根目录 .env 加载凭据，逐一调用 IDXClient 的所有方法，
打印结果摘要并捕获异常。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# 让 dx_client 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

# 加载项目根目录的 .env
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

from dx_client import DXClient, DXCohortInfo, DXCohortError, default_dx_client_config
from dx_client.dx_exceptions import DXDatabaseNotFoundError

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results: list[tuple[str, str, str]] = []


def report(method: str, status: str, detail: str = "") -> None:
    tag = {"pass": PASS, "fail": FAIL, "skip": SKIP}[status]
    print(f"  {tag}  {method}" + (f"  — {detail}" if detail else ""))
    results.append((method, status, detail))


def test_connect(client: DXClient) -> None:
    try:
        client.connect()
        report("connect()", "pass")
    except Exception as e:
        report("connect()", "fail", str(e))


def test_properties(client: DXClient) -> None:
    try:
        pid = client.current_project_id
        conn = client.is_connected
        report("current_project_id", "pass", pid)
        report("is_connected", "pass", str(conn))
    except Exception as e:
        report("properties", "fail", str(e))


def test_list_projects(client: DXClient) -> None:
    try:
        projects = client.list_projects()
        report("list_projects()", "pass", f"{len(projects)} projects")
        for p in projects[:5]:
            print(f"         {p.id}  {p.name}")
        if len(projects) > 5:
            print(f"         ... and {len(projects) - 5} more")
    except Exception as e:
        report("list_projects()", "fail", str(e))


def test_get_project(client: DXClient) -> None:
    try:
        proj = client.get_project(client.current_project_id)
        report("get_project()", "pass", f"{proj.id} {proj.name}")
    except Exception as e:
        report("get_project()", "fail", str(e))


def test_set_project(client: DXClient) -> None:
    try:
        client.set_project(client.current_project_id)
        report("set_project()", "pass")
    except Exception as e:
        report("set_project()", "fail", str(e))


def test_list_files(client: DXClient) -> None:
    try:
        files = client.list_files(limit=10)
        report("list_files()", "pass", f"{len(files)} files")
        for f in files[:5]:
            print(f"         {f.id}  {f.name}  ({f.folder})")
    except Exception as e:
        report("list_files()", "fail", str(e))


def test_describe_file(client: DXClient) -> None:
    try:
        files = client.list_files(limit=1)
        if not files:
            report("describe_file()", "skip", "no files in project")
            return
        info = client.describe_file(files[0].id)
        report("describe_file()", "pass", f"{info.id} {info.name} size={info.size}")
    except Exception as e:
        report("describe_file()", "fail", str(e))


def test_download_file(client: DXClient) -> None:
    try:
        files = client.list_files(limit=1)
        if not files:
            report("download_file()", "skip", "no files in project")
            return
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            local = client.download_file(files[0].id, str(Path(tmpdir) / "test_download"))
            report("download_file()", "pass", f"-> {local}")
    except Exception as e:
        report("download_file()", "fail", str(e))


def test_list_records(client: DXClient) -> None:
    try:
        records = client.list_records(limit=10)
        report("list_records()", "pass", f"{len(records)} records")
        for r in records[:5]:
            print(f"         {r.id}  {r.name}  types={r.types}")
    except Exception as e:
        report("list_records()", "fail", str(e))


def test_get_record(client: DXClient) -> None:
    try:
        records = client.list_records(limit=1)
        if not records:
            report("get_record()", "skip", "no records in project")
            return
        rec = client.get_record(records[0].id)
        detail_keys = list(rec.details.keys()) if rec.details else []
        report("get_record()", "pass", f"{rec.id} details_keys={detail_keys[:5]}")
    except Exception as e:
        report("get_record()", "fail", str(e))


def test_find_data_objects(client: DXClient) -> None:
    try:
        objs = client.find_data_objects(classname="record", limit=5)
        report("find_data_objects(record)", "pass", f"{len(objs)} objects")
        for o in objs[:3]:
            print(f"         {o.id}  {o.name}  class={o.classname}")
    except Exception as e:
        report("find_data_objects()", "fail", str(e))


def test_list_databases(client: DXClient) -> None:
    try:
        dbs = client.list_databases(limit=10)
        report("list_databases()", "pass", f"{len(dbs)} databases")
        for d in dbs:
            print(f"         {d.id}  {d.name}  state={d.state}")
    except Exception as e:
        report("list_databases()", "fail", str(e))


def test_get_database(client: DXClient) -> None:
    try:
        dbs = client.list_databases(limit=1)
        if not dbs:
            report("get_database()", "skip", "no databases in project")
            return
        info = client.get_database(dbs[0].id)
        report("get_database()", "pass", f"{info.id} {info.name}")
    except Exception as e:
        report("get_database()", "fail", str(e))


def test_find_database(client: DXClient) -> None:
    try:
        db = client.find_database()
        report("find_database()", "pass", f"{db.id} {db.name}")
    except DXDatabaseNotFoundError as e:
        report("find_database()", "skip", str(e))
    except Exception as e:
        report("find_database()", "fail", str(e))


def test_describe_database_cluster(client: DXClient) -> None:
    try:
        dbs = client.list_databases(limit=1)
        if not dbs:
            report("describe_database_cluster()", "skip", "no databases")
            return
        desc = client.describe_database_cluster(dbs[0].id)
        keys = list(desc.keys())
        report("describe_database_cluster()", "pass", f"keys={keys}")
        for k, v in desc.items():
            print(f"         {k}: {v}")
    except Exception as e:
        report("describe_database_cluster()", "fail", str(e))


def test_get_database_schema(client: DXClient) -> None:
    try:
        db = client.find_database()
    except DXDatabaseNotFoundError:
        report("get_database_schema()", "skip", "no database found")
        return
    except Exception as e:
        report("get_database_schema()", "fail", f"find_database: {e}")
        return

    try:
        tables = client.get_database_schema(db.id)
        report("get_database_schema()", "pass", f"{len(tables)} tables")
        for t in tables[:10]:
            print(f"         {t.name}")
        if len(tables) > 10:
            print(f"         ... and {len(tables) - 10} more")
    except Exception as e:
        report("get_database_schema()", "fail", str(e))


def test_query_database(client: DXClient) -> None:
    try:
        db = client.find_database()
    except DXDatabaseNotFoundError:
        report("query_database()", "skip", "no database found")
        return
    except Exception as e:
        report("query_database()", "fail", f"find_database: {e}")
        return

    try:
        df = client.query_database(db.id, ["participant.eid", "participant.p31"])
        report("query_database()", "pass", f"{len(df)} rows x {len(df.columns)} cols")
        print(f"         columns: {list(df.columns)}")
        print(df.head(2).to_string(index=False))
    except Exception as e:
        report("query_database()", "fail", str(e))


def test_download_database_query(client: DXClient) -> None:
    try:
        db = client.find_database()
    except DXDatabaseNotFoundError:
        report("download_database_query()", "skip", "no database found")
        return
    except Exception as e:
        report("download_database_query()", "fail", f"find_database: {e}")
        return

    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = str(Path(tmpdir) / "test_query.csv")
            path = client.download_database_query(db.id, out, ["participant.eid", "participant.p31"])
            size = path.stat().st_size
            report("download_database_query()", "pass", f"-> {path} ({size} bytes)")
    except Exception as e:
        report("download_database_query()", "fail", str(e))


def test_find_dataset(client: DXClient) -> None:
    try:
        ds_id, ds_ref = client.find_dataset()
        report("find_dataset()", "pass", f"{ds_id} ref={ds_ref}")
    except Exception as e:
        report("find_dataset()", "fail", str(e))


def test_get_data_dictionary(client: DXClient) -> None:
    try:
        df = client.get_data_dictionary()
        report("get_data_dictionary()", "pass", f"{len(df)} fields, cols={list(df.columns)}")
        print(df.head(3).to_string(index=False))
    except Exception as e:
        report("get_data_dictionary()", "fail", str(e))


def test_list_fields(client: DXClient) -> None:
    # 1. 无过滤：列出全部（只看前几行）
    try:
        df = client.list_fields()
        report("list_fields()", "pass", f"{len(df)} fields, cols={list(df.columns)}")
        print(df.head(3).to_string(index=False))
    except Exception as e:
        report("list_fields()", "fail", str(e))

    # 2. 按 entity 过滤
    try:
        df = client.list_fields(entity="participant")
        report("list_fields(entity=participant)", "pass", f"{len(df)} fields")
        print(df.head(3).to_string(index=False))
    except Exception as e:
        report("list_fields(entity=participant)", "fail", str(e))

    # 3. 按名称模糊匹配
    try:
        df = client.list_fields(name_pattern="p31")
        report("list_fields(name_pattern=p31)", "pass", f"{len(df)} fields")
        print(df.to_string(index=False))
    except Exception as e:
        report("list_fields(name_pattern=p31)", "fail", str(e))


def test_extract_fields(client: DXClient) -> None:
    try:
        _, ref = client.find_dataset()
    except Exception as e:
        report("extract_fields()", "skip", f"find_dataset: {e}")
        return

    try:
        df = client.extract_fields(["participant.eid", "participant.p31"], dataset_ref=ref)
        report("extract_fields()", "pass", f"{len(df)} rows x {len(df.columns)} cols")
        print(f"         columns: {list(df.columns)}")
        print(df.head(2).to_string(index=False))
    except Exception as e:
        report("extract_fields()", "fail", str(e))


def test_disconnect(client: DXClient) -> None:
    try:
        client.disconnect()
        report("disconnect()", "pass")
    except Exception as e:
        report("disconnect()", "fail", str(e))


def test_create_cohort(client: DXClient) -> None:
    """端到端测试：创建 cohort 并验证 record 类型和 details。"""
    import time

    try:
        _, ds_ref = client.find_dataset()
    except Exception as e:
        report("create_cohort()", "skip", f"find_dataset: {e}")
        return

    cohort_name = f"_test_cohort_{int(time.time())}"
    test_eids = ["1000010", "1000025", "1000055"]
    created_id: str | None = None

    try:
        # 使用 validate=False 避免慢速的 vizserver 数据查询
        test_fields = ["participant.eid", "participant.p31", "participant.p21003"]
        info = client.create_cohort(
            name=cohort_name,
            participant_ids=test_eids,
            dataset_ref=ds_ref,
            folder="/",
            description="dx_client e2e test cohort (auto cleanup)",
            validate=False,
            entity_fields=test_fields,
        )
        created_id = info.id
        assert isinstance(info, DXCohortInfo)
        assert info.id.startswith("record-")
        assert info.participant_count == len(test_eids)
        report(
            "create_cohort()", "pass",
            f"id={info.id} name={info.name} participants={info.participant_count}",
        )

        # 验证返回的 entity_fields
        assert info.entity_fields == test_fields
        report("create_cohort() entity_fields in return", "pass",
               f"fields={info.entity_fields}")

        # 验证 record 类型
        rec = client.get_record(info.id)
        types = rec.types or []
        has_cohort = "CohortBrowser" in types
        report("create_cohort() verify type", "pass" if has_cohort else "fail",
               f"types={types}")

        # 验证 details 包含必要字段
        details = rec.details or {}
        has_sql = "sql" in details and len(details["sql"]) > 0
        has_filters = "filters" in details
        has_dataset = "dataset" in details
        has_fields = details.get("fields") == test_fields
        ok = has_sql and has_filters and has_dataset
        report("create_cohort() verify details", "pass" if ok else "fail",
               f"sql={has_sql} filters={has_filters} dataset={has_dataset}")
        report("create_cohort() verify details.fields", "pass" if has_fields else "fail",
               f"fields={details.get('fields')}")

    except DXCohortError as e:
        report("create_cohort()", "fail", f"DXCohortError: {e}")
    except Exception as e:
        report("create_cohort()", "fail", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # 清理：尝试删除测试 cohort record
    if created_id:
        try:
            import dxpy
            dxpy.DXHTTPRequest(
                "/%s/remove" % created_id,
                {"project": client.current_project_id},
            )
            report("create_cohort() cleanup", "pass", f"removed {created_id}")
        except Exception as e:
            report("create_cohort() cleanup", "skip", f"{created_id}: {e}")


def test_create_cohort_with_filters(client: DXClient) -> None:
    """端到端测试：通过 pheno_filters 创建 cohort 并验证 record。"""
    import time

    try:
        _, ds_ref = client.find_dataset()
    except Exception as e:
        report("create_cohort(filters)", "skip", f"find_dataset: {e}")
        return

    cohort_name = f"_test_cohort_filters_{int(time.time())}"
    created_id: str | None = None

    try:
        filters = {
            "logic": "and",
            "pheno_filters": {
                "logic": "and",
                "compound": [
                    {
                        "name": "phenotype",
                        "logic": "and",
                        "filters": {
                            "participant$p31": [{"condition": "is", "values": "Female"}],
                        },
                    }
                ],
            },
        }
        info = client.create_cohort(
            name=cohort_name,
            filters=filters,
            dataset_ref=ds_ref,
            description="dx_client e2e test cohort with filters (auto cleanup)",
        )
        created_id = info.id
        assert isinstance(info, DXCohortInfo)
        assert info.id.startswith("record-")
        report("create_cohort(filters)", "pass", f"id={info.id} name={info.name}")

        # 验证 record 类型和 details
        rec = client.get_record(info.id)
        types = rec.types or []
        has_cohort = "CohortBrowser" in types
        report("create_cohort(filters) verify type", "pass" if has_cohort else "fail",
               f"types={types}")

        details = rec.details or {}
        has_sql = "sql" in details and len(details["sql"]) > 0
        has_filters = "filters" in details
        ok = has_sql and has_filters
        report("create_cohort(filters) verify details", "pass" if ok else "fail",
               f"sql={has_sql} filters={has_filters}")

    except DXCohortError as e:
        report("create_cohort(filters)", "fail", f"DXCohortError: {e}")
    except Exception as e:
        report("create_cohort(filters)", "fail", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    # 清理
    if created_id:
        try:
            import dxpy
            dxpy.DXHTTPRequest(
                "/%s/remove" % created_id,
                {"project": client.current_project_id},
            )
            report("create_cohort(filters) cleanup", "pass", f"removed {created_id}")
        except Exception as e:
            report("create_cohort(filters) cleanup", "skip", f"{created_id}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 70)
    print("  DXClient 全方法可用性测试")
    print("=" * 70)

    client = DXClient(default_dx_client_config)

    tests = [
        test_connect,
        test_properties,
        test_list_projects,
        test_get_project,
        test_set_project,
        test_list_files,
        test_describe_file,
        test_download_file,
        test_list_records,
        test_get_record,
        test_find_data_objects,
        test_list_databases,
        test_get_database,
        test_find_database,
        test_describe_database_cluster,
        test_get_database_schema,
        test_query_database,
        test_download_database_query,
        test_find_dataset,
        test_get_data_dictionary,
        test_list_fields,
        test_extract_fields,
        test_create_cohort,
        test_create_cohort_with_filters,
        test_disconnect,
    ]

    for t in tests:
        name = t.__name__
        print(f"\n── {name} ──")
        try:
            t(client)
        except Exception as e:
            report(name, "fail", f"unhandled: {e}\n{traceback.format_exc()}")

    # 摘要
    print("\n" + "=" * 70)
    print("  测试摘要")
    print("=" * 70)
    passed = sum(1 for _, s, _ in results if s == "pass")
    failed = sum(1 for _, s, _ in results if s == "fail")
    skipped = sum(1 for _, s, _ in results if s == "skip")
    print(f"  {PASS} {passed}   {FAIL} {failed}   {SKIP} {skipped}   total {len(results)}")

    if failed:
        print("\n  失败项:")
        for name, status, detail in results:
            if status == "fail":
                print(f"    - {name}: {detail}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
