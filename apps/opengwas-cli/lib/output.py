from __future__ import annotations

import json
import shutil

import pandas as pd
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
    df: pd.DataFrame,
    columns: list[str] | None = None,
    title: str | None = None,
    column_width: dict[str, int] | None = None,
) -> None:
    """Render a DataFrame as a rich table, auto-fitting to terminal width.

    Args:
        column_width: 指定列的最大宽度，未指定的列仍使用默认截断。
                    例如 {"trait": 0} 表示 trait 列不截断。
    """
    if df.empty:
        console.print("[dim]No results found.[dim]")
        return

    if columns:
        available = [c for c in columns if c in df.columns]
        if available:
            df = df[available]

    num_cols = len(df.columns)
    if num_cols == 0:
        console.print("[dim]No columns to display.[/dim]")
        return

    available_width = _term_width - 3 - 2 * num_cols

    # 计算每列宽度
    col_widths: list[int] = []
    for col in df.columns:
        if column_width and col in column_width:
            # 0 表示不截断，用终端剩余宽度（最小 10）
            cw = max(10, available_width - sum(col_widths))
        else:
            cw = min(_MAX_CELL, max(8, available_width // num_cols))
        col_widths.append(cw)

    table = Table(title=title, show_lines=False, header_style="bold cyan")
    for col, cw in zip(df.columns, col_widths):
        table.add_column(col, max_width=cw, no_wrap=True)

    for _, row in df.iterrows():
        values = [_truncate(row[col], cw) for col, cw in zip(df.columns, col_widths)]
        table.add_row(*values)

    console.print(table)
    console.print(f"[dim]Total: {len(df)} row(s)[/dim]")


def print_json(data: object) -> None:
    """Render data as formatted JSON."""
    if isinstance(data, pd.DataFrame):
        data = data.to_dict(orient="records")
    console.print_json(json.dumps(data, default=str, ensure_ascii=False))


def print_success(message: str) -> None:
    console.print(f"[bold green]{message}[/bold green]")


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
