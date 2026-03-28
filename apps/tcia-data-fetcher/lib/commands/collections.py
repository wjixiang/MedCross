from __future__ import annotations

import typer
from rich.console import Console

from lib.output import print_error, print_json, print_table
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Query and explore TCIA collections")
console = Console()

_json = typer.Option(False, "--json", help="Output as JSON")


@app.command("list")
def list_collections(
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """List all available TCIA collections."""
    client = TCIAApiClient()
    df = client.get_collections()
    if limit > 0:
        df = df.head(limit)
    if json_output:
        print_json(df)
    else:
        print_table(df, title="TCIA Collections")


@app.command("describe")
def describe_collection(
    name: str = typer.Argument(help="Collection name"),
    json_output: bool = _json,
):
    """Show collection description and patient count."""
    client = TCIAApiClient()
    desc_df = client.get_collection_descriptions()
    count_df = client.get_collection_patient_counts()

    match = desc_df[desc_df.iloc[:, 0].astype(str).str.contains(name, case=False, na=False)]
    if match.empty:
        print_error(f"Collection '{name}' not found.")
        raise typer.Exit(1)

    counts = count_df[count_df.iloc[:, 0].astype(str).str.contains(name, case=False, na=False)]

    if json_output:
        result = match.iloc[0].to_dict()
        if not counts.empty:
            result["PatientCount"] = int(counts.iloc[0, 1])
        print_json([result])
    else:
        console.print(f"[bold]{name}[/bold]")
        console.print(match.iloc[0].to_string())
        if not counts.empty:
            console.print(f"\n[bold]Patient count:[/bold] {int(counts.iloc[0, 1])}")
