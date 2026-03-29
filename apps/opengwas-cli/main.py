from __future__ import annotations

import typer

from lib.commands import assoc, info, ld, phewas, status, tophits, variants

app = typer.Typer(
    name="opengwas",
    help="IEU OpenGWAS CLI — query GWAS datasets, associations, variants, and LD from the OpenGWAS database.",
    no_args_is_help=True,
)

app.add_typer(status.app, name="status")
app.add_typer(info.app, name="info")
app.add_typer(assoc.app, name="assoc")
app.add_typer(tophits.app, name="tophits")
app.add_typer(phewas.app, name="phewas")
app.add_typer(variants.app, name="variants")
app.add_typer(ld.app, name="ld")


if __name__ == "__main__":
    app()
