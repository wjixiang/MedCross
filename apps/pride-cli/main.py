from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import typer

from lib.commands import ap, download, files, info, proteins, search, stats

app = typer.Typer(
    name="pride",
    help="PRIDE Archive CLI — search and retrieve proteomics project metadata.",
    no_args_is_help=True,
)

app.add_typer(search.app, name="search")
app.add_typer(info.app, name="info")
app.add_typer(download.app, name="download")
app.add_typer(files.app, name="files")
app.add_typer(proteins.app, name="proteins")
app.add_typer(stats.app, name="stats")
app.add_typer(ap.app, name="ap")

if __name__ == "__main__":
    app()
