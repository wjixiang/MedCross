import typer

from lib.output import print_error, print_json, print_table
from lib.pride_api_client import (
    get_all_project_files,
    get_file,
    get_file_checksums,
    get_file_counts_by_type,
    get_project_file_count,
    get_project_files,
    get_sdrf_files,
    get_total_file_count,
)

app = typer.Typer(help="Manage PRIDE project files.")

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def list(
    accession: str = typer.Argument(help="PRIDE project accession, e.g. PXD046193"),
    page: int = typer.Option(0, "--page", "-p", help="Page number (0-indexed)."),
    page_size: int = typer.Option(
        50, "--page-size", "-n", help="Number of results per page."
    ),
    filter: str = typer.Option("", "--filter", help="Filter files by name pattern."),
    json_output: bool = _json,
):
    """List all files in a project."""
    try:
        files = get_project_files(
            accession, page=page, page_size=page_size, filename_filter=filter
        )
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json([f.model_dump() for f in files])
        return

    if not files:
        return

    rows = []
    for f in files:
        size_mb = f.fileSizeBytes / (1024 * 1024) if f.fileSizeBytes else 0
        rows.append(
            {
                "Accession": f.accession,
                "FileName": f.fileName,
                "Size(MB)": f"{size_mb:.2f}" if size_mb else "N/A",
                "Type": f.fileExtension,
                "Downloads": f.totalDownloads,
            }
        )

    print_table(
        rows,
        title=f"Files — {accession}",
        column_width={
            "Accession": 16,
            "FileName": 50,
            "Size(MB)": 10,
            "Type": 8,
            "Downloads": 10,
        },
    )


@app.command()
def count(
    accession: str = typer.Argument(help="PRIDE project accession."),
):
    """Show file count for a project."""
    try:
        count = get_project_file_count(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    from lib.output import console

    console.print(f"[cyan]{accession}[/cyan] has [bold]{count}[/bold] file(s)")


@app.command()
def types(
    accession: str = typer.Argument(help="PRIDE project accession."),
    json_output: bool = _json,
):
    """Show file type counts for a project."""
    try:
        counts = get_file_counts_by_type(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(counts)
        return

    rows = [{"Extension": ext, "Count": cnt} for ext, cnt in counts.items()]
    print_table(rows, title=f"File Types — {accession}")


@app.command()
def sdrf(
    accession: str = typer.Argument(help="PRIDE project accession."),
    json_output: bool = _json,
):
    """Get SDRF (Sample to Data Relationship File) for a project."""
    try:
        files = get_sdrf_files(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(files)
        return

    from lib.output import console

    if files:
        console.print(f"[bold]SDRF file(s) for {accession}:[/bold]")
        for f in files:
            console.print(f"  {f}")
    else:
        console.print(f"[dim]No SDRF files found for {accession}[/dim]")


@app.command()
def checksum(
    accession: str = typer.Argument(help="PRIDE project accession."),
):
    """Get MD5 checksums for all files in a project."""
    try:
        checksums = get_file_checksums(accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    from lib.output import console

    console.print(checksums)


@app.command()
def total(
    json_output: bool = _json,
):
    """Show total number of files across all PRIDE projects."""
    try:
        total = get_total_file_count()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    from lib.output import console

    if json_output:
        print_json({"total_files": total})
    else:
        console.print(f"[bold]Total files in PRIDE:[/bold] [cyan]{total:,}[/cyan]")


@app.command()
def detail(
    file_accession: str = typer.Argument(
        help="PRIDE file accession, e.g. PXD046193F001"
    ),
    json_output: bool = _json,
):
    """Get detailed metadata for a single file."""
    try:
        f = get_file(file_accession)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(f.model_dump())
        return

    from lib.output import console
    from rich.panel import Panel
    from rich.text import Text

    text = Text()
    text.append("File Name: ", style="bold")
    text.append(f.fileName)
    text.append("\nAccession: ", style="bold")
    text.append(f.accession)
    text.append("\nProject(s): ", style="bold")
    text.append(", ".join(f.projectAccessions) if f.projectAccessions else "N/A")
    text.append("\nSize (bytes): ", style="bold")
    text.append(f"{f.fileSizeBytes:,}" if f.fileSizeBytes else "N/A")
    text.append("\nExtension: ", style="bold")
    text.append(f.fileExtension or "N/A")
    text.append("\nCompressed: ", style="bold")
    text.append(str(f.compress) if f.compress is not None else "N/A")
    text.append("\nChecksum: ", style="bold")
    text.append(f.checksum or "N/A")
    text.append("\nDownloads: ", style="bold")
    text.append(str(f.totalDownloads))
    if f.submissionDate:
        text.append("\nSubmitted: ", style="bold")
        text.append(str(f.submissionDate))
    if f.publicationDate:
        text.append("\nPublished: ", style="bold")
        text.append(str(f.publicationDate))

    console.print(Panel(text, title=f"[bold]{f.accession}[/bold]", border_style="blue"))
