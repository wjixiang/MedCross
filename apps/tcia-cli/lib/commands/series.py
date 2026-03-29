from __future__ import annotations

import typer

from lib.output import print_json, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Query and inspect DICOM series")

_json = typer.Option(False, "--json", help="Output as JSON")

# Default columns shown in series list (subset for readability)
_SERIES_COLUMNS = [
    "Collection", "PatientID", "StudyDate", "Modality",
    "BodyPartExamined", "SeriesNumber", "ImageCount", "FileSize",
    "SeriesInstanceUID",
]


@app.command("list")
def list_series(
    collection: str = typer.Option("", "-c", "--collection", help="Collection name"),
    modality: str = typer.Option("", "-m", "--modality", help="Modality (CT, MR, ...)"),
    body_part: str = typer.Option("", "-b", "--body-part", help="Body part examined"),
    patient_id: str = typer.Option("", "-p", "--patient-id", help="Patient ID"),
    study_uid: str = typer.Option("", "-s", "--study-uid", help="Study Instance UID"),
    manufacturer: str = typer.Option("", "--manufacturer", help="Manufacturer"),
    model: str = typer.Option("", "--model", help="Manufacturer model name"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
    offset: int = typer.Option(0, "--offset", help="Skip first N rows"),
    all_columns: bool = typer.Option(False, "--all", help="Show all columns"),
):
    """Query DICOM series with optional filters."""
    client = TCIAApiClient()
    df = client.get_series(
        collection=collection,
        patient_id=patient_id,
        study_uid=study_uid,
        modality=modality,
        body_part=body_part,
        manufacturer=manufacturer,
        model=model,
    )
    if offset > 0:
        df = df.iloc[offset:]
    if limit > 0:
        df = df.head(limit)
    if json_output:
        print_json(df)
    else:
        cols = None if all_columns else _SERIES_COLUMNS
        print_table(df, columns=cols, title="Series")


@app.command("meta")
def series_meta(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    json_output: bool = _json,
):
    """Show detailed metadata for a series."""
    client = TCIAApiClient()
    df = client.get_series_meta(series_uid)
    if json_output:
        print_json(df)
    else:
        print_table(df, title=f"Series Metadata: {series_uid}")


@app.command("size")
def series_size(
    series_uid: str = typer.Argument(help="Series Instance UID"),
):
    """Show file count and total size for a series."""
    client = TCIAApiClient()
    df = client.get_series_size(series_uid)
    print_table(df, title=f"Series Size: {series_uid}")


@app.command("sop")
def sop_uids(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """List SOP Instance UIDs in a series."""
    client = TCIAApiClient()
    df = client.get_sop_instance_uids(series_uid)
    if limit > 0:
        df = df.head(limit)
    if json_output:
        print_json(df)
    else:
        print_table(df, title=f"SOP Instances in {series_uid}")
