from __future__ import annotations

import typer

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_table

app = typer.Typer(help="Query variant-trait associations")

_json = typer.Option(False, "--json", help="Output as JSON")

_ASSOC_COLUMNS = [
    "id", "rsid", "chromosome", "position", "ea", "oa",
    "beta", "se", "pval", "eaf", "samplesize",
]


@app.command()
def query(
    variants: list[str] = typer.Argument(help="Variant rsIDs or chr:pos (hg19/b37), e.g. rs1205 7:105561135"),
    studies: list[str] = typer.Option([], "--study", "-s", help="GWAS study IDs"),
    proxies: bool = typer.Option(False, "--proxies", help="Look for proxy SNPs"),
    population: str = typer.Option("EUR", "--pop", help="Reference population (AFR/AMR/EAS/EUR/SAS)"),
    r2: float = typer.Option(0.8, "--r2", help="Minimum LD r2 for proxies"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """Query variant associations from GWAS datasets.

    Variants support rsID (rs1205), chr:pos (7:105561135), or chr:pos range (7:105561135-105563135).
    """
    if not studies:
        print_error("At least one --study ID is required. Use 'opengwas info list' to browse datasets.")
        raise typer.Exit(1)

    client = get_client()
    try:
        result = client.get_associations(
            variant=variants,
            id=studies,
            proxies=1 if proxies else 0,
            population=population,
            r2=r2,
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
        print_table(df, columns=_ASSOC_COLUMNS, title="Variant Associations")
