from __future__ import annotations

import typer
from rich.console import Console

from lib.output import print_error, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Generate summary reports")
console = Console()


@app.command("doi")
def doi_report(
    uids: list[str] = typer.Argument(help="Series Instance UID(s)"),
):
    """Generate DOI summary report for series."""
    client = TCIAApiClient()
    try:
        df = client.report_doi_summary(uids)
        print_table(df, title="DOI Summary Report")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("collection")
def collection_report(
    collection: str = typer.Option(..., "-c", "--collection", help="Collection name"),
):
    """Generate collection summary report."""
    client = TCIAApiClient()
    try:
        df = client.report_collection_summary(collection)
        print_table(df, title=f"Collection Report: {collection}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
