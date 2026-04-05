"""ukb-mcp CLI — 预热缓存等离线工具。"""

from __future__ import annotations

import argparse
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from dx_client import DXClient, DXClientConfig, DXConfigError
from dx_client.cache import DuckDBCache
from ukb_mcp.config import get_settings


def cmd_warm(args: argparse.Namespace) -> None:
    """预热缓存：连接 DNAnexus 并加载指定数据。"""
    settings = get_settings()

    cache = DuckDBCache(settings.cache_db_path)
    client = DXClient(
        config=DXClientConfig(
            auth_token=settings.dx_auth_token,
            project_context_id=settings.dx_project_context_id,
            api_server_host=settings.dx_api_server_host,
            api_server_port=settings.dx_api_server_port,
            api_server_protocol=settings.dx_api_server_protocol,
        ),
        cache=cache,
    )

    try:
        client.connect()
    except DXConfigError as e:
        print(f"连接失败: {e}", file=sys.stderr)
        sys.exit(1)

    project = client.current_project_id or "(未设置)"
    print(f"已连接 DNAnexus  项目: {project}")
    print(f"缓存文件: {settings.cache_db_path}")
    print()

    targets = set(args.targets) if args.targets else {"fields"}

    if "fields" in targets:
        print("预热数据字典...")
        t0 = time.time()
        try:
            df = client.get_data_dictionary(refresh=True)
            elapsed = time.time() - t0
            print(f"  完成: {len(df)} 个字段  ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  失败: {e}", file=sys.stderr)

    if "schema" in targets:
        print("预热数据库 schema...")
        t0 = time.time()
        try:
            db = client.find_database(refresh=True)
            tables = client.get_database_schema(db.id, refresh=True)
            elapsed = time.time() - t0
            print(f"  完成: {len(tables)} 张表  ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  失败: {e}", file=sys.stderr)

    if "databases" in targets:
        print("预热数据库列表...")
        t0 = time.time()
        try:
            dbs = client.list_databases(refresh=True)
            elapsed = time.time() - t0
            print(f"  完成: {len(dbs)} 个数据库  ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  失败: {e}", file=sys.stderr)

    if "all" in targets:
        print("预热项目文件列表...")
        t0 = time.time()
        try:
            files = client.list_files(limit=1000, refresh=True)
            elapsed = time.time() - t0
            print(f"  完成: {len(files)} 个文件  ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  失败: {e}", file=sys.stderr)

    print()
    print(f"缓存状态: {cache.info()}")

    client.disconnect()


def cmd_cache_info(args: argparse.Namespace) -> None:
    """查看缓存统计信息。"""
    settings = get_settings()
    cache = DuckDBCache(settings.cache_db_path)
    info = cache.info()
    for k, v in info.items():
        print(f"  {k}: {v}")
    cache.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ukb-mcp",
        description="UK Biobank 数据服务 CLI",
    )
    sub = parser.add_subparsers(dest="command")

    p_warm = sub.add_parser("warm", help="预热缓存")
    p_warm.add_argument(
        "targets",
        nargs="*",
        choices=["fields", "schema", "databases", "all"],
        default=["fields"],
        help="预热目标，默认 fields。可多选。",
    )

    sub.add_parser("cache-info", help="查看缓存统计")

    args = parser.parse_args()
    if args.command == "warm":
        cmd_warm(args)
    elif args.command == "cache-info":
        cmd_cache_info(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
