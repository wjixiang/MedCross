from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from lib.output import print_error, print_success, print_warning
from pymr.data_loader import StudyMetadata, vcf_to_zarr

app = typer.Typer(help="Convert GWAS VCF.gz files to Zarr format for efficient loading")


@app.callback(invoke_without_command=True)
def convert(
    ctx: typer.Context,
    ids: list[str] = typer.Argument(
        help="GWAS dataset IDs to convert (e.g. ebi-a-GCST90093110 ukb-e-574_CSA)",
    ),
    data_dir: str | None = typer.Option(
        None, "-d", "--data-dir",
        help="Directory containing VCF.gz files (default: OPENGWAS_DATA_DIR env var)",
    ),
    output_dir: str | None = typer.Option(
        None, "-o", "--output",
        help="Output directory for Zarr files (default: same as data-dir)",
    ),
    chunk_size: int = typer.Option(
        500_000, "--chunk-size",
        help="Number of variants per Zarr chunk",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing Zarr files",
    ),
):
    """Convert downloaded GWAS VCF.gz files to Zarr format.

    Expects each dataset in a subdirectory with .vcf.gz and .tbi files:
        data_dir/
            ebi-a-GCST90093110/
                ebi-a-GCST90093110.vcf.gz
                ebi-a-GCST90093110.vcf.gz.tbi
    """
    if ctx.invoked_subcommand is not None:
        return

    src_dir: Path = Path(data_dir) if data_dir else Path(os.environ.get("OPENGWAS_DATA_DIR", "gwas-data"))
    zarr_dir: Path = Path(output_dir) if output_dir else src_dir

    # 查找所有待转换的 VCF.gz 文件
    tasks: list[tuple[Path, Path]] = []
    for study_id in ids:
        vcf_path = src_dir / study_id / f"{study_id}.vcf.gz"

        if not vcf_path.exists():
            print_error(f"VCF 文件不存在: {vcf_path}")
            raise typer.Exit(1)

        tbi_path = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
        if not tbi_path.exists():
            print_error(f"Tabix 索引不存在: {tbi_path}")
            raise typer.Exit(1)

        zarr_path = zarr_dir / f"{study_id}.zarr"
        if zarr_path.exists() and not force:
            print_warning(f"Skip (exists): {zarr_path}")
            continue

        if zarr_path.exists() and force:
            shutil.rmtree(zarr_path)

        tasks.append((vcf_path, zarr_path))

    if not tasks:
        print_success("Nothing to convert.")
        return

    console = Console()
    console.print(f"[bold]Converting {len(tasks)} dataset(s) to Zarr...[/bold]\n")

    results: list[tuple[str, StudyMetadata, float]] = []
    for vcf_path, zarr_path in tasks:
        study_id = vcf_path.parent.name
        console.print(f"[bold cyan]>>> {study_id}[/bold cyan]")

        t0 = time.time()
        try:
            meta = vcf_to_zarr(vcf_path, zarr_path, chunk_size=chunk_size)
        except Exception as e:
            print_error(f"{study_id}: {e}")
            raise typer.Exit(1)

        elapsed = time.time() - t0
        results.append((study_id, meta, elapsed))

    # 汇总结果
    console.print()
    t = Table(title="Conversion Summary", show_lines=True, header_style="bold cyan")
    t.add_column("Dataset", style="bold")
    t.add_column("Type", justify="center")
    t.add_column("Variants", justify="right")
    t.add_column("Time", justify="right")
    t.add_column("Zarr Size", justify="right")

    for study_id, meta, elapsed in results:
        zarr_size = _dir_size(zarr_dir / f"{study_id}.zarr")
        t.add_row(
            study_id,
            meta.study_type,
            f"{meta.total_variants:,}",
            f"{elapsed:.1f}s",
            _human_size(zarr_size),
        )

    console.print(t)


def _dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def _human_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
