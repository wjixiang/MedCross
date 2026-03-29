from __future__ import annotations

import typer
from rich.console import Console

from lib.gwas_api_client import get_client
from lib.output import print_error, print_json

app = typer.Typer(help="Check API service status")
console = Console()


@app.callback(invoke_without_command=True)
def status_default(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show API status and current user info (default when no subcommand)."""
    if ctx.invoked_subcommand is not None:
        return

    client = get_client()
    try:
        services = client.get_status()
        user_info = client.get_user()
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    if json_output:
        print_json({"services": services, "user": user_info})
        return

    console.print("[bold]API Services[/bold]")
    for service, ok in services.items() if isinstance(services, dict) else []:
        icon = "[green]OK[/green]" if ok else "[red]DOWN[/red]"
        console.print(f"  {icon}  {service}")

    user = user_info.get("user", {})
    console.print()
    console.print("[bold]User[/bold]")
    console.print(f"  Name:     {user.get('first_name', '')} {user.get('last_name', '')}")
    console.print(f"  Email:    {user.get('uid', 'N/A')}")
    console.print(f"  Token valid until: {user.get('jwt_valid_until', 'N/A')}")


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
