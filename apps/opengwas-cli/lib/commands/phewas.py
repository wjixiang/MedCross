from __future__ import annotations

import typer

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_table

app = typer.Typer(help="Phenome-wide association study (PheWAS)")

_json = typer.Option(False, "--json", help="Output as JSON")

_PHEWAS_COLUMNS = [
    "id", "trait", "rsid", "chromosome", "position",
    "ea", "oa", "beta", "se", "pval", "samplesize",
]


@app.command()
def run(
    variants: list[str] = typer.Argument(help="Variant rsIDs or chr:pos (hg19/b37)"),
    pval: float = typer.Option(0.01, "--pval", "-p", help="P-value threshold (must be <= 0.01)"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """PheWAS of specified variants across all available GWAS datasets."""
    client = get_client()
    try:
        result = client.get_phewas(variant=variants, pval=pval)
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
        print_table(df, columns=_PHEWAS_COLUMNS, title="PheWAS Results")
