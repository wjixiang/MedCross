from __future__ import annotations

import typer

from lib.output import print_error, print_json, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Query patients in TCIA collections")

_json = typer.Option(False, "--json", help="Output as JSON")


@app.command("list")
def list_patients(
    collection: str = typer.Option(..., "-c", "--collection", help="Collection name"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """List patients in a collection."""
    client = TCIAApiClient()
    df = client.get_patients(collection)
    if limit > 0:
        df = df.head(limit)
    if json_output:
        print_json(df)
    else:
        print_table(df, title=f"Patients in {collection}")


@app.command("by-modality")
def patients_by_modality(
    collection: str = typer.Option(..., "-c", "--collection", help="Collection name"),
    modality: str = typer.Option(..., "-m", "--modality", help="Modality (e.g. CT, MR)"),
    json_output: bool = _json,
):
    """List patients filtered by collection and modality."""
    client = TCIAApiClient()
    df = client.get_patients_by_modality(collection, modality)
    if json_output:
        print_json(df)
    else:
        print_table(df, title=f"Patients ({collection}, {modality})")


@app.command("new")
def new_patients(
    collection: str = typer.Option(..., "-c", "--collection", help="Collection name"),
    date: str = typer.Option(..., "-d", "--date", help="Date in YYYY/MM/DD format"),
    json_output: bool = _json,
):
    """List patients added to a collection since a date."""
    client = TCIAApiClient()
    df = client.get_new_patients(collection, date)
    if json_output:
        print_json(df)
    else:
        print_table(df, title=f"New patients in {collection} since {date}")
