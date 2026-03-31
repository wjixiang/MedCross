import typer

from lib.output import console, print_error, print_json, print_table
from lib.pride_api_client import (
    get_project_count,
    get_stats,
    get_submissions_monthly,
    get_submissions_monthly_tsv,
    get_submitted_data_stats,
)

app = typer.Typer(help="View PRIDE Archive statistics.")

_json = typer.Option(False, "--json", help="Output as JSON.")


@app.command()
def project_count(json_output: bool = _json):
    """Total number of projects in PRIDE."""
    try:
        count = get_project_count()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json({"total_projects": count})
    else:
        console.print(f"[bold]Total PRIDE projects:[/bold] [cyan]{count:,}[/cyan]")


@app.command()
def stats(
    name: str = typer.Argument(
        help="Statistic name, e.g. 'projectCount', 'fileCount'."
    ),
    json_output: bool = _json,
):
    """Retrieve a named statistic from PRIDE."""
    try:
        result = get_stats(name)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(result)
    else:
        console.print(result)


@app.command()
def monthly(
    json_output: bool = _json,
):
    """Monthly submission counts (JSON format)."""
    try:
        result = get_submissions_monthly()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(result)
        return

    if isinstance(result, dict):
        rows = [{"Month": k, "Count": v} for k, v in result.items()]
    elif isinstance(result, list):
        rows = result
    else:
        console.print(str(result))
        return
    print_table(rows, title="Monthly Submissions")


@app.command()
def monthly_tsv():
    """Monthly submission counts (TSV format)."""
    try:
        result = get_submissions_monthly_tsv()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    console.print(result)


@app.command()
def data_stats(json_output: bool = _json):
    """Submitted data size statistics by month."""
    try:
        result = get_submitted_data_stats()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    if json_output:
        print_json(result)
    else:
        console.print(result)
