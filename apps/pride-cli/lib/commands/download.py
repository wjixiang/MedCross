from __future__ import annotations

import ftplib
from pathlib import Path

import typer
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from config import PrideCliConfig
from lib.ftpUtils import download_dir, parse_ftp_url
from lib.output import print_error, print_success, print_warning
from lib.pride_api_client import get_project_download_links

app = typer.Typer(help="Download PRIDE project data.")


@app.command()
def links(
    accession: str = typer.Argument(help="PRIDE project accession, e.g. PXD046193"),
):
    """Show download links for a project."""
    try:
        result = get_project_download_links(accession=accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    from rich.table import Table
    from rich.console import Console

    console = Console()
    table = Table(title=f"Download Links — {accession}")
    table.add_column("Protocol", style="bold cyan")
    table.add_column("URL")
    table.add_row("FTP", result.ftp)
    table.add_row("Globus", result.globus)
    console.print(table)


@app.command()
def project(
    accession: str = typer.Argument(help="PRIDE project accession, e.g. PXD046193"),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Local output directory (default: DATASET_PATH/<accession>)",
    ),
) -> None:
    """Download a PRIDE project via FTP."""
    try:
        result = get_project_download_links(accession=accession)
    except Exception as e:
        print_error(f"Failed to fetch download links: {e}")
        raise typer.Exit(1)

    host, remote_dir = parse_ftp_url(result.ftp)
    if not host or not remote_dir:
        print_error(f"Invalid FTP URL: {result.ftp}")
        raise typer.Exit(1)

    local_root = (
        Path(output) if output else Path(PrideCliConfig.datasetPath) / accession
    )

    from rich.console import Console

    console = Console()
    console.print(f"[bold]Downloading [cyan]{accession}[/cyan] from FTP[/bold]")
    console.print(f"  Host:    {host}")
    console.print(f"  Remote:  {remote_dir}")
    console.print(f"  Local:   {local_root}")
    console.print()

    progress = Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    try:
        ftp = ftplib.FTP(host, timeout=300)
        ftp.login()  # anonymous login
        ftp.cwd(remote_dir)

        with progress:
            download_dir(ftp, ".", local_root, progress)

        ftp.quit()
    except ftplib.all_errors as e:
        print_error(f"FTP error: {e}")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_warning("Download interrupted by user.")
        raise typer.Exit(130)

    print_success(f"Download complete: {local_root}")
