from __future__ import annotations

import typer

from lib.output import print_error, print_json, print_table
from lib.pride_api_client import search_projects
from pride_client.models import PRIDESearchQuery

app = typer.Typer(help="Search PRIDE projects by keyword.")

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def projects(
    keyword: str = typer.Argument(help="Search keyword, e.g. 'proteome'"),
    filter: str = typer.Option(
        "projectTitle",
        "--filter", "-f",
        help="Filter field: projectTitle, projectDescription, etc.",
    ),
    page_size: int = typer.Option(
        20, "--page-size", "-n", help="Number of results per page.",
    ),
    page: int = typer.Option(0, "--page", "-p", help="Page number (0-indexed)."),
    asc: bool = typer.Option(False, "--asc", help="Sort ascending (default descending)."),
    wrap: bool = typer.Option(False, "--wrap", help="Truncate inline context to fit column width."),
    json_output: bool = _json,
):
    """Search PRIDE projects by keyword."""
    query = PRIDESearchQuery(
        keyword=keyword,
        filter=filter,
        pageSize=page_size,
        page=page,
        sortDirection="ASC" if asc else "DESC",
    )

    try:
        results, total = search_projects(query)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json([r.model_dump() for r in results])
        return

    if not results:
        return

    rows = []
    for p in results:
        submitters = ", ".join(p.submitters[:2])
        if len(p.submitters) > 2:
            submitters += f" +{len(p.submitters) - 2}"
        rows.append({
            "Accession": p.accession,
            "Title": p.title,
            "Submitters": submitters,
            "Date": p.submissionDate,
            "Downloads": p.downloadCount,
        })

    print_table(
        rows,
        title=f"PRIDE Search Results ({len(results)} projects)",
        column_width={"Accession": 12, "Title": 60, "Submitters": 20},
        wrap=wrap,
        total=total,
        page=page,
        page_size=page_size,
    )
