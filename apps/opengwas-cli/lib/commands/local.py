from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import typer
from rich.table import Table

from lib.output import console, print_error, print_warning

app = typer.Typer(help="Browse locally downloaded GWAS datasets")


def _get_data_dir(data_dir: str | None) -> Path:
    if data_dir:
        return Path(data_dir)
    env_dir = os.environ.get("OPENGWAS_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path("gwas-data")


def _scan_local(data_dir: Path) -> pd.DataFrame:
    """扫描本地目录，收集每个数据集的状态信息。"""
    rows: list[dict] = []
    if not data_dir.exists():
        return pd.DataFrame(rows)

    for entry in sorted(data_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name

        # 查找 VCF.gz 和 Zarr
        vcf = entry / f"{name}.vcf.gz"
        tbi = entry / f"{name}.vcf.gz.tbi"
        zarr_dir = entry / f"{name}.zarr"

        has_vcf = vcf.exists()
        has_tbi = tbi.exists()
        has_zarr = zarr_dir.exists()

        # 跳过既无 VCF 也无 Zarr 的目录（如 .zarr 直接放在根目录）
        if not has_vcf and not has_zarr:
            continue

        # 尝试从 zarr attrs 读取元信息
        meta: dict = {}
        if has_zarr:
            try:
                import zarr as zarr_mod
                g = zarr_mod.open(str(zarr_dir), mode="r")
                meta = dict(g.attrs)
            except Exception:
                pass

        # 尝试从 VCF header 解析（无 zarr 时）
        if not meta and has_vcf and has_tbi:
            try:
                from cyvcf2 import VCF
                v = VCF(str(vcf))
                for line in v.raw_header.split("\n"):
                    if line.startswith("##SAMPLE"):
                        import re
                        inner = re.search(r'<(.+)>$', line)
                        if inner:
                            fields = re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s>]+))', inner.group(1))
                            meta = {k: (v2 if v2 else v1) for k, v1, v2 in fields}
                        break
                v.close()
            except Exception:
                pass

        vcf_size = vcf.stat().st_size if has_vcf else 0
        zarr_size = 0
        if has_zarr:
            for f in zarr_dir.rglob("*"):
                if f.is_file():
                    zarr_size += f.stat().st_size

        rows.append({
            "id": name,
            "status": "zarr" if has_zarr else ("vcf" if has_vcf and has_tbi else "incomplete"),
            "type": meta.get("study_type", ""),
            "variants": meta.get("total_variants", ""),
            "cases": meta.get("total_cases", ""),
            "controls": meta.get("total_controls", ""),
            "vcf_size": _human_size(vcf_size),
            "zarr_size": _human_size(zarr_size) if has_zarr else "",
        })

    return pd.DataFrame(rows)


def _human_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@app.callback(invoke_without_command=True)
def local(
    ctx: typer.Context,
    data_dir: str | None = typer.Option(
        None, "-d", "--data-dir",
        help="Data directory (default: OPENGWAS_DATA_DIR env var, or './gwas-data')",
    ),
):
    """Browse locally downloaded GWAS datasets."""
    if ctx.invoked_subcommand is not None:
        return

    list_local(data_dir)


@app.command("list")
def list_local(
    data_dir: str | None = typer.Option(
        None, "-d", "--data-dir",
        help="Data directory (default: OPENGWAS_DATA_DIR env var, or './gwas-data')",
    ),
):
    """List all locally downloaded datasets."""
    base = _get_data_dir(data_dir)
    df = _scan_local(base)

    if df.empty:
        print_warning(f"No datasets found in {base}")
        return

    # 格式化数字列
    for col in ("variants", "cases", "controls"):
        df[col] = df[col].apply(lambda x: f"{int(float(x)):,}" if x and str(x) != "" else "")

    # 状态着色
    status_color = {"zarr": "green", "vcf": "yellow", "incomplete": "red"}
    table = Table(title=f"Local Datasets — {base}", show_lines=True, header_style="bold cyan")
    table.add_column("ID", style="bold", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Variants", justify="right")
    table.add_column("Cases", justify="right")
    table.add_column("Controls", justify="right")
    table.add_column("VCF Size", justify="right")
    table.add_column("Zarr Size", justify="right")

    for _, row in df.iterrows():
        st = str(row["status"])
        color = status_color.get(st, "white")
        table.add_row(
            str(row["id"]),
            f"[{color}]{st}[/{color}]",
            str(row["type"]),
            str(row["variants"]),
            str(row["cases"]),
            str(row["controls"]),
            str(row["vcf_size"]),
            str(row["zarr_size"]),
        )

    console.print(table)
    console.print(f"[dim]Total: {len(df)} dataset(s)[/dim]")


@app.command("show")
def show_local(
    ids: list[str] = typer.Argument(help="Local dataset IDs to show"),
    data_dir: str | None = typer.Option(
        None, "-d", "--data-dir",
        help="Data directory (default: OPENGWAS_DATA_DIR env var, or './gwas-data')",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed info for local datasets."""
    base = _get_data_dir(data_dir)
    df = _scan_local(base)

    if df.empty:
        print_warning(f"No datasets found in {base}")
        return

    df = df[df["id"].isin(ids)]
    if df.empty:
        print_error(f"Dataset(s) not found locally: {', '.join(ids)}")
        raise typer.Exit(1)

    if json_output:
        console.print_json(json.dumps(df.to_dict(orient="records"), default=str, ensure_ascii=False))  # type: ignore[call-overload]
        return

    for _, row in df.iterrows():
        name = str(row["id"])
        study_dir = base / name
        zarr_path = study_dir / f"{name}.zarr"

        table = Table(title=f"Dataset: {name}", show_lines=True, header_style="bold cyan")
        table.add_column("Property", style="bold", max_width=20)
        table.add_column("Value", max_width=60)

        props: list[tuple[str, str]] = [
            ("Status", str(row["status"])),
            ("Type", str(row["type"])),
            ("Total Variants", str(row["variants"])),
            ("Cases", str(row["cases"])),
            ("Controls", str(row["controls"])),
            ("VCF Size", str(row["vcf_size"])),
            ("Zarr Size", str(row["zarr_size"])),
        ]

        # 从 zarr attrs 读取更多字段
        if zarr_path.exists():
            try:
                import zarr
                g = zarr.open(str(zarr_path), mode="r")
                attrs = dict(g.attrs)
                props.append(("Source VCF", str(attrs.get("source_vcf", ""))))
                props.append(("Format Fields", str(attrs.get("format_fields", ""))))
                props.append(("Harmonised", str(attrs.get("harmonised_variants", ""))))
            except Exception:
                pass

        for k, v in props:
            if v and v != "":
                table.add_row(k, v)

        console.print(table)
        console.print()
