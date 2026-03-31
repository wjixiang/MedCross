import typer

from lib.output import print_error, print_json, print_table
from lib.pride_api_client import (
    get_all_protein_accessions,
    get_protein_by_accession,
    search_proteins,
)

app = typer.Typer(help="Query proteins associated with PRIDE projects.")

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def by_accession(
    accession: str = typer.Argument(help="UniProt protein accession, e.g. P02768"),
    json_output: bool = _json,
):
    """Find all PRIDE projects containing a specific protein."""
    try:
        result = get_protein_by_accession(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(result.model_dump())
        return

    from lib.output import console

    console.print(f"[bold]Protein:[/bold] [cyan]{result.proteinAccession}[/cyan]")
    console.print(f"[bold]Projects ({len(result.projects)}):[/bold]")
    for p in result.projects:
        console.print(f"  {p}")


@app.command()
def search(
    accession: str = typer.Argument(help="UniProt protein accession, e.g. P02768"),
    json_output: bool = _json,
):
    """Search protein details by accession (alternative endpoint)."""
    try:
        results = search_proteins(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json([r.model_dump() for r in results])
        return

    if not results:
        from lib.output import console

        console.print(f"[dim]No results for {accession}[/dim]")
        return

    rows = []
    for r in results:
        rows.append(
            {
                "Protein": r.proteinAccession,
                "Projects": ", ".join(r.projects[:5])
                + (f" +{len(r.projects) - 5}" if len(r.projects) > 5 else ""),
            }
        )
    print_table(rows, title=f"Protein Search — {accession}")


@app.command()
def list_accessions(
    page: int = typer.Option(0, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(100, "--page-size", "-n", help="Results per page."),
    json_output: bool = _json,
):
    """List all protein accessions in PRIDE with pagination."""
    try:
        result = get_all_protein_accessions(page_size=page_size, page_number=page)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(result.model_dump())
        return

    from lib.output import console

    total_pages = result.totalPages
    console.print(
        f"[bold]Total:[/bold] {result.totalElements:,} protein accessions | "
        f"Page {page + 1}/{total_pages + 1 if total_pages else 1}"
    )
    for acc in result.accessions:
        console.print(f"  {acc}")
