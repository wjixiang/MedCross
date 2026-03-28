from __future__ import annotations

import typer

from lib.output import print_error, print_json, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Inspect DICOM tags and segmentation references")

_json = typer.Option(False, "--json", help="Output as JSON")


@app.command("tags")
def dicom_tags(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    json_output: bool = _json,
):
    """Show DICOM tags for a series."""
    client = TCIAApiClient()
    try:
        df = client.get_dicom_tags(series_uid)
        if json_output:
            print_json(df)
        else:
            print_table(df, title=f"DICOM Tags: {series_uid}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("seg-ref")
def seg_ref(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    json_output: bool = _json,
):
    """Show reference series for a SEG or RTSTRUCT."""
    client = TCIAApiClient()
    try:
        df = client.get_seg_ref_series(series_uid)
        if json_output:
            print_json(df)
        else:
            print_table(df, title=f"SEG/RTSTRUCT Reference: {series_uid}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
