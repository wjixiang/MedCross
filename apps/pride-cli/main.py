from __future__ import annotations

import typer

from lib.commands import search, info

app = typer.Typer(
    name="pride",
    help="PRIDE Archive CLI — search and retrieve proteomics project metadata.",
    no_args_is_help=True,
)

app.add_typer(search.app, name="search")
app.add_typer(info.app, name="info")

if __name__ == "__main__":
    app()
