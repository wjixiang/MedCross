from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import typer

from lib.commands import search, info, download

app = typer.Typer(
    name="pride",
    help="PRIDE Archive CLI — search and retrieve proteomics project metadata.",
    no_args_is_help=True,
)

app.add_typer(search.app, name="search")
app.add_typer(info.app, name="info")
app.add_typer(download.app, name='download')

if __name__ == "__main__":
    app()
