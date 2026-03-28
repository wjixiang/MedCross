from __future__ import annotations

import typer

from lib.output import print_json, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Advanced search across TCIA collections")

_json = typer.Option(False, "--json", help="Output as JSON")


@app.callback(invoke_without_command=True)
def search(
    ctx: typer.Context,
    collections: list[str] = typer.Option([], "-c", "--collection", help="Collection name(s)"),
    modalities: list[str] = typer.Option([], "-m", "--modality", help="Modality(ies)"),
    body_parts: list[str] = typer.Option([], "-b", "--body-part", help="Body part(ies)"),
    manufacturers: list[str] = typer.Option([], "--manufacturer", help="Manufacturer(s)"),
    from_date: str = typer.Option("", "--from-date", help="Start date (YYYY/MM/DD)"),
    to_date: str = typer.Option("", "--to-date", help="End date (YYYY/MM/DD)"),
    patients: list[str] = typer.Option([], "-p", "--patient", help="Patient ID(s)"),
    min_studies: int = typer.Option(0, "--min-studies", help="Minimum number of studies"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    offset: int = typer.Option(0, "--offset", help="Skip first N results"),
    json_output: bool = _json,
):
    """Search TCIA with multiple filters."""
    if ctx.invoked_subcommand:
        return

    client = TCIAApiClient()
    df = client.simple_search(
        collections=collections,
        modalities=modalities,
        body_parts=body_parts,
        manufacturers=manufacturers,
        from_date=from_date,
        to_date=to_date,
        patients=patients,
        min_studies=min_studies,
        limit=limit,
        offset=offset,
    )
    if json_output:
        print_json(df)
    else:
        print_table(df, title="Search Results")
