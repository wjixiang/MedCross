from __future__ import annotations

import typer
from rich.console import Console

from lib.output import print_error, print_success
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Download DICOM images from TCIA")
console = Console()


@app.command("series")
def download_series(
    uids: list[str] = typer.Argument(help="Series Instance UID(s)"),
    output_dir: str = typer.Option("tciaDownload", "-o", "--output", help="Download directory"),
    zip_flag: bool = typer.Option(False, "--zip", help="Keep as ZIP (do not extract)"),
    hash_flag: bool = typer.Option(False, "--hash", help="Verify with MD5 hash"),
    workers: int = typer.Option(10, "--workers", "-w", help="Max parallel downloads"),
    number: int = typer.Option(0, "--number", "-n", help="Limit images per series (0 = all)"),
):
    """Download one or more DICOM series."""
    client = TCIAApiClient()
    console.print(f"[bold]Downloading {len(uids)} series to {output_dir}...[/bold]")
    try:
        client.download_series(
            series_data=uids,
            path=output_dir,
            as_zip=zip_flag,
            with_hash=hash_flag,
            max_workers=workers,
            number=number,
        )
        print_success("Download complete.")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("image")
def download_image(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    sop_uid: str = typer.Argument(help="SOP Instance UID"),
    output_dir: str = typer.Option("", "-o", "--output", help="Output directory"),
):
    """Download a single DICOM image."""
    client = TCIAApiClient()
    try:
        client.download_image(series_uid=series_uid, sop_uid=sop_uid, path=output_dir)
        print_success("Image downloaded.")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
