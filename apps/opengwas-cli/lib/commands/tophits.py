from __future__ import annotations

import typer

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_table

app = typer.Typer(help="Extract top hits from GWAS datasets")

_json = typer.Option(False, "--json", help="Output as JSON")

_TOPHITS_COLUMNS = [
    "id", "rsid", "chromosome", "position", "ea", "oa",
    "beta", "se", "pval", "eaf", "samplesize",
]


@app.command()
def extract(
    studies: list[str] = typer.Argument(help="GWAS study IDs, e.g. ieu-a-2"),
    pval: float = typer.Option(5e-8, "--pval", "-p", help="P-value threshold (must be <= 0.01)"),
    clump: bool = typer.Option(True, "--clump/--no-clump", help="Perform LD clumping"),
    r2: float = typer.Option(0.001, "--r2", help="Clumping r2 threshold"),
    kb: int = typer.Option(5000, "--kb", help="Clumping window size in kb"),
    pop: str = typer.Option("EUR", "--pop", help="Population for clumping"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """Extract top hits by p-value threshold from GWAS datasets."""
    client = get_client()
    try:
        result = client.get_top_hits(
            id=studies,
            pval=pval,
            clump=1 if clump else 0,
            r2=r2,
            kb=kb,
            pop=pop,
        )
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if limit > 0:
        df = df.head(limit)

    if json_output:
        print_json(df)
    else:
        print_table(df, columns=_TOPHITS_COLUMNS, title="Top Hits")
