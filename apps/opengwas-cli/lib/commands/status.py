from __future__ import annotations

import typer
from rich.console import Console

from lib.gwas_api_client import get_client
from lib.output import print_error, print_json

app = typer.Typer(help="Check API service status")
console = Console()


@app.command()
def check(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Check if OpenGWAS API services are running."""
    client = get_client()
    try:
        result = client.get_status()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    if json_output:
        print_json(result)
    else:
        for service, status in result.items() if isinstance(result, dict) else []:
            icon = "[green]OK[/green]" if status else "[red]DOWN[/red]"
            console.print(f"  {icon}  {service}")


@app.command()
def user(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Get current user info and validate token."""
    client = get_client()
    try:
        result = client.get_user()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    if json_output:
        print_json(result)
    else:
        user = result.get("user", {})
        console.print(f"[bold]User:[/bold]     {user.get('uid', 'N/A')}")
        console.print(f"[bold]Name:[/bold]     {user.get('first_name', '')} {user.get('last_name', '')}")
        console.print(f"[bold]Roles:[/bold]    {', '.join(user.get('roles', [])) or 'None'}")
        console.print(f"[bold]Tags:[/bold]     {', '.join(user.get('tags', [])) or 'None'}")
        console.print(f"[bold]Token valid until:[/bold] {user.get('jwt_valid_until', 'N/A')}")
