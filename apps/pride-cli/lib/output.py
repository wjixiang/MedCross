from __future__ import annotations

import json
import shutil

from rich.console import Console
from rich.table import Table

console = Console()

_term_width = shutil.get_terminal_size(fallback=(120, 40)).columns
_MAX_CELL = 30


def _truncate(val: object, max_width: int) -> str:
    s = str(val) if val is not None and str(val) != "nan" else ""
    if len(s) > max_width:
        return s[: max_width - 3] + "..."
    return s


def print_table(
    rows: list[dict],
    columns: list[str] | None = None,
    title: str | None = None,
    column_width: dict[str, int] | None = None,
    wrap: bool = False,
    total: int | None = None,
    page: int = 0,
    page_size: int = 20,
) -> None:
    """Render a list of dicts as a rich table, auto-fitting to terminal width."""
    if not rows:
        console.print("[dim]No results found.[/dim]")
        return

    keys = list(rows[0].keys())
    if columns:
        available = [c for c in columns if c in keys]
        if available:
            keys = available

    num_cols = len(keys)
    if num_cols == 0:
        console.print("[dim]No columns to display.[/dim]")
        return

    available_width = _term_width - 3 - 2 * num_cols

    col_widths: list[int] = []
    flexible_count = num_cols
    reserved = 0
    for col in keys:
        if column_width and col in column_width:
            reserved += column_width[col]
            flexible_count -= 1
    flexible_width = (available_width - reserved) // max(flexible_count, 1)

    for col in keys:
        if column_width and col in column_width:
            cw = column_width[col]
        else:
            cw = min(_MAX_CELL, max(8, flexible_width))
        col_widths.append(cw)

    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for col, cw in zip(keys, col_widths):
        table.add_column(col, min_width=len(col), max_width=cw, no_wrap=not wrap)

    for row in rows:
        if wrap :
            values = [str(row.get(col)) for col in keys]
        else:
            values = [_truncate(row.get(col), cw) for col, cw in zip(keys, col_widths)]
        table.add_row(*values)

    console.print(table)
    if total is not None and total > 0:
        total_pages = (total + page_size - 1) // page_size
        console.print(f"[dim]Total: {total} result(s), Page {page + 1}/{total_pages} ({len(rows)} row(s) shown)[/dim]")
    else:
        console.print(f"[dim]Total: {len(rows)} row(s)[/dim]")


def print_json(data: object) -> None:
    """Render data as formatted JSON."""
    console.print_json(json.dumps(data, default=str, ensure_ascii=False))


def print_success(message: str) -> None:
    console.print(f"[bold green]{message}[/bold green]")


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
