from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_success, print_warning

app = typer.Typer(help="Download GWAS summary statistics files")


@app.callback(invoke_without_command=True)
def download(
    ctx: typer.Context,
    ids: list[str] = typer.Argument(help="GWAS dataset IDs to download"),
    output_dir: str | None = typer.Option(
        None, "-o", "--output",
        help="Download directory (default: OPENGWAS_DATA_DIR env var, or './gwas-data')",
    ),
    proxy: str = typer.Option(
        "", "--proxy",
        help="HTTP proxy for downloads (default: auto-detect from env)",
    ),
):
    """Download GWAS summary statistics files (.vcf.gz, .tbi, _report.html).

    Downloads to OPENGWAS_DATA_DIR or -o/--output directory.
    Skips files that already exist.
    """
    if ctx.invoked_subcommand is not None:
        return

    # 确定下载目录
    dir_path = Path(output_dir) if output_dir else Path(os.environ.get("OPENGWAS_DATA_DIR", "gwas-data"))
    dir_path.mkdir(parents=True, exist_ok=True)

    # 获取下载链接
    client = get_client()
    try:
        result = client.get_gwas_files(ids)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if df.empty:
        print_error("No download URLs found for the given datasets.")
        raise typer.Exit(1)

    # 构建下载任务列表，跳过已存在的文件
    tasks: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        url: str = row["url"]
        dataset_id: str = row["id"]
        filename = url.split("/")[-1]
        filepath = dir_path / dataset_id / filename
        if filepath.exists():
            print_warning(f"Skip (exists): {filepath}")
        else:
            tasks.append((url, str(filepath)))

    if not tasks:
        print_success("All files already downloaded.")
        return

    # 检测代理
    download_proxy: str | None = proxy or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or None

    console = Console()
    console.print(f"[bold]Downloading {len(tasks)} file(s) to {dir_path}...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TaskProgressColumn(),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("download", total=len(tasks))

        with httpx.Client(timeout=300.0, proxy=download_proxy) as dl_client:
            for url, filepath in tasks:
                dest = Path(filepath)
                dest.parent.mkdir(parents=True, exist_ok=True)

                tmp_path = dest.with_suffix(".tmp")
                dl_task = None
                try:
                    with dl_client.stream("GET", url, follow_redirects=True) as resp:
                        resp.raise_for_status()
                        total = int(resp.headers.get("content-length", 0))
                        dl_task = progress.add_task(dest.name, total=total or None)

                        with open(tmp_path, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=1024 * 64):
                                f.write(chunk)
                                progress.update(dl_task, advance=len(chunk))

                        tmp_path.rename(dest)
                except Exception as e:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    console.print(f"[red]  Failed: {dest.name} — {e}[/red]")
                finally:
                    progress.update(task_id, advance=1)
                    if dl_task is not None:
                        try:
                            progress.remove_task(dl_task)
                        except Exception:
                            pass
    console.print()
    print_success(f"Downloaded to {dir_path}")
