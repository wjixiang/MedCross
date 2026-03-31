import typer

from lib.output import console, print_error, print_json, print_table
from lib.pride_api_client import get_ap_project, search_ap_projects, search_ap_proteins
from pride_client.models import PRIDEAPProteinSearchQuery, PRIDEAPSearchQuery

app = typer.Typer(
    help="Affinity Purification (AP) projects — protein-protein interactions."
)

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def project(
    accession: str = typer.Argument(help="AP project accession, e.g. PRD000001"),
    json_output: bool = _json,
):
    """Get detailed metadata for an AP project."""
    try:
        ap = get_ap_project(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(ap.model_dump())
        return

    from rich.panel import Panel
    from rich.text import Text

    text = Text()
    text.append("Title: ", style="bold")
    text.append(ap.title)
    text.append("\nAccession: ", style="bold")
    text.append(ap.accession)
    text.append("\nDOI: ", style="bold")
    text.append(ap.doi or "N/A")
    text.append("\nSubmission Date: ", style="bold")
    text.append(ap.submissionDate)
    text.append("\nPublication Date: ", style="bold")
    text.append(ap.publicationDate or "N/A")
    text.append("\nKeywords: ", style="bold")
    text.append(", ".join(ap.keywords) or "N/A")
    text.append("\n\nSubmitters: ", style="bold")
    text.append(", ".join(ap.submitters) or "N/A")
    text.append("\nInstruments: ", style="bold")
    text.append(", ".join(ap.instruments) or "N/A")
    text.append("\nOrganisms: ", style="bold")
    text.append(", ".join(ap.organisms) or "N/A")
    text.append("\n\nProteins: ", style="bold")
    text.append(f"{ap.noOfProteins:,}" if ap.noOfProteins else "N/A")
    text.append("  Samples: ", style="bold")
    text.append(f"{ap.noOfSamples:,}" if ap.noOfSamples else "N/A")
    text.append("  Download Count: ", style="bold")
    text.append(str(ap.downloadCount))

    console.print(
        Panel(text, title=f"[bold]{ap.accession}[/bold]", border_style="green")
    )

    if ap.projectDescription:
        console.print("\n[bold]Description:[/bold]")
        console.print(ap.projectDescription)


@app.command()
def search(
    keyword: str = typer.Argument(help="Search keyword."),
    page: int = typer.Option(0, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(20, "--page-size", "-n", help="Results per page."),
    asc: bool = typer.Option(False, "--asc", help="Sort ascending."),
    json_output: bool = _json,
):
    """Search AP projects by keyword."""
    query = PRIDEAPSearchQuery(
        keyword=keyword,
        pageSize=page_size,
        page=page,
        sortDirection="ASC" if asc else "DESC",
    )
    try:
        results = search_ap_projects(query)
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
        rows.append(
            {
                "Accession": p.accession,
                "Title": p.title,
                "Proteins": p.noOfProteins,
                "Samples": p.noOfSamples,
                "Downloads": p.downloadCount,
            }
        )

    print_table(
        rows,
        title=f"AP Project Search — '{keyword}'",
        column_width={
            "Accession": 12,
            "Title": 60,
            "Proteins": 10,
            "Samples": 10,
            "Downloads": 10,
        },
    )


@app.command()
def proteins(
    accession: str = typer.Argument(help="AP project accession."),
    keyword: str = typer.Option(
        "", "--keyword", "-k", help="Filter proteins by keyword."
    ),
    page: int = typer.Option(0, "--page", "-p", help="Page number."),
    page_size: int = typer.Option(50, "--page-size", "-n", help="Results per page."),
    json_output: bool = _json,
):
    """List proteins in an AP project."""
    query = PRIDEAPProteinSearchQuery(
        projectAccession=accession,
        keyword=keyword,
        pageSize=page_size,
        page=page,
    )
    try:
        results = search_ap_proteins(query)
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
        rows.append(
            {
                "Accession": p.proteinAccession,
                "Name": p.proteinName,
                "Gene": p.gene,
                "Projects": p.projectCount,
            }
        )

    print_table(
        rows,
        title=f"AP Proteins — {accession}",
        column_width={"Accession": 14, "Name": 40, "Gene": 12, "Projects": 10},
    )
