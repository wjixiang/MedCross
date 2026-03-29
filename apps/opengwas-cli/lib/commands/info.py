from __future__ import annotations

import typer

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_success, print_table

app = typer.Typer(help="Query GWAS dataset metadata")

_json = typer.Option(False, "--json", help="Output as JSON")

_INFO_COLUMNS = [
    "id", "trait", "author", "year", "sample_size",
    "nsnp", "category", "population", "sex",
]


@app.command("list")
def list_datasets(
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
    trait: str = typer.Option("", "--trait", "-t", help="Filter by trait name (case-insensitive substring)"),
    category: str = typer.Option("", "--category", "-c", help="Filter by category"),
    author: str = typer.Option("", "--author", "-a", help="Filter by author"),
):
    """List all accessible GWAS datasets."""
    client = get_client()
    try:
        result = client.get_all_gwas_info()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)

    if trait:
        df = df[df["trait"].astype(str).str.contains(trait, case=False, na=False)]
    if category:
        df = df[df["category"].astype(str).str.contains(category, case=False, na=False)]
    if author:
        df = df[df["author"].astype(str).str.contains(author, case=False, na=False)]

    if limit > 0:
        df = df.head(limit)

    if json_output:
        print_json(df)
    else:
        print_table(df, columns=_INFO_COLUMNS, title="GWAS Datasets")


@app.command("show")
def show_dataset(
    ids: list[str] = typer.Argument(help="GWAS dataset IDs, e.g. ieu-a-2 ieu-a-7"),
    json_output: bool = _json,
):
    """Show metadata for specific GWAS datasets."""
    client = get_client()
    try:
        result = client.get_gwas_info(ids)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)

    if json_output:
        print_json(df)
    else:
        print_table(df, columns=_INFO_COLUMNS, title="GWAS Dataset Info")


@app.command("files")
def get_files(
    ids: list[str] = typer.Argument(help="GWAS dataset IDs"),
    json_output: bool = _json,
):
    """Get download URLs for dataset files (.vcf.gz, .tbi, _report.html).

    URLs expire in 2 hours.
    """
    client = get_client()
    try:
        result = client.get_gwas_files(ids)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)

    if json_output:
        print_json(df)
    else:
        print_table(df, title="Download URLs")
        if not df.empty:
            print_success("Note: URLs expire in 2 hours.")
