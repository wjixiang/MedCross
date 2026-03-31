from __future__ import annotations

import typer
from rich.panel import Panel
from rich.text import Text

from lib.output import console, print_error, print_json
from lib.pride_api_client import get_project

app = typer.Typer(help="Get detailed project information.")

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def project(
    accession: str = typer.Argument(help="PRIDE project accession, e.g. 'PXD046193'"),
    json_output: bool = _json,
):
    """Retrieve detailed metadata for a single PRIDE project."""
    try:
        p = get_project(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(p.model_dump())
        return

    # Submitters
    submitter_lines = []
    for s in p.submitters:
        submitter_lines.append(f"  {s.name} ({s.affiliation})")

    # Instruments
    instrument_names = [i.name for i in p.instruments]

    # Experiment types
    exp_types = [e.name for e in p.experimentTypes]

    # Organisms
    organism_names = [o.name for o in p.organisms]

    text = Text()
    text.append("Title: ", style="bold")
    text.append(p.title, style="cyan")
    text.append("\nDOI: ", style="bold")
    text.append(p.doi or "N/A")
    text.append("\nSubmission Type: ", style="bold")
    text.append(p.submissionType)
    text.append("\nLicense: ", style="bold")
    text.append(p.license or "N/A")
    text.append("\nSubmission Date: ", style="bold")
    text.append(p.submissionDate)
    text.append("\nPublication Date: ", style="bold")
    text.append(p.publicationDate)
    text.append("\nTotal Downloads: ", style="bold")
    text.append(str(p.totalFileDownloads))
    text.append("\nKeywords: ", style="bold")
    text.append(", ".join(p.keywords) or "N/A")
    text.append("\n\nSubmitters:\n", style="bold")
    text.append("\n".join(submitter_lines) or "  N/A")
    text.append("\n\nInstruments: ", style="bold")
    text.append(", ".join(instrument_names) or "N/A")
    text.append("\nExperiment Types: ", style="bold")
    text.append(", ".join(exp_types) or "N/A")
    text.append("\nOrganisms: ", style="bold")
    text.append(", ".join(organism_names) or "N/A")
    text.append("\nCountries: ", style="bold")
    text.append(", ".join(p.countries) or "N/A")

    console.print(Panel(text, title=f"[bold]{p.accession}[/bold]", border_style="blue"))

    if p.projectDescription:
        console.print("\n[bold]Project Description:[/bold]")
        console.print(p.projectDescription)
