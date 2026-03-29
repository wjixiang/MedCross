from __future__ import annotations

import typer

from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_table

app = typer.Typer(help="Query variant information")

_json = typer.Option(False, "--json", help="Output as JSON")

_VARIANT_COLUMNS = ["rsid", "ID", "CHROM", "POS", "REF", "ALT"]


@app.command("rsid")
def by_rsid(
    rsids: list[str] = typer.Argument(help="rs IDs, e.g. rs1205 rs234"),
    json_output: bool = _json,
):
    """Lookup variant info by rs IDs."""
    client = get_client()
    try:
        result = client.get_variants_by_rsid(rsids)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if json_output:
        print_json(df)
    else:
        print_table(df, columns=_VARIANT_COLUMNS, title="Variant Info (by rsID)")


@app.command("chrpos")
def by_chrpos(
    positions: list[str] = typer.Argument(help="chr:pos (hg19/b37), e.g. 7:105561135"),
    radius: int = typer.Option(0, "--radius", "-r", help="Search range (bp) either side of target"),
    json_output: bool = _json,
):
    """Lookup variant info by chromosome position (hg19/b37).

    Supports range queries, e.g. 7:105561135-105563135.
    """
    client = get_client()
    try:
        result = client.get_variants_by_chrpos(positions, radius=radius)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if json_output:
        print_json(df)
    else:
        print_table(df, columns=_VARIANT_COLUMNS, title="Variant Info (by chr:pos)")


@app.command("gene")
def by_gene(
    gene: str = typer.Argument(help="Ensembl ID (ENSG00000123374) or Entrez ID (1017)"),
    radius: int = typer.Option(0, "--radius", "-r", help="Search range (bp) either side of gene"),
    json_output: bool = _json,
    limit: int = typer.Option(0, "--limit", "-n", help="Max rows (0 = unlimited)"),
):
    """Lookup variants within a gene region."""
    client = get_client()
    try:
        result = client.get_variants_by_gene(gene, radius=radius)
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
        print_table(df, columns=_VARIANT_COLUMNS, title=f"Variants in {gene}")


@app.command("afl2")
def allele_freq(
    rsids: list[str] = typer.Option([], "--rsid", "-r", help="rs IDs"),
    chrpos: list[str] = typer.Option([], "--chrpos", "-c", help="chr:pos (hg19/b37)"),
    radius: int = typer.Option(0, "--radius", help="Search range for chrpos (bp)"),
    json_output: bool = _json,
):
    """Get allele frequency and LD scores for variants."""
    if not rsids and not chrpos:
        print_error("Provide at least one --rsid or --chrpos.")
        raise typer.Exit(1)

    client = get_client()
    try:
        result = client.get_variants_afl2(
            rsid=rsids or None,
            chrpos=chrpos or None,
            radius=radius,
        )
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if json_output:
        print_json(df)
    else:
        print_table(df, title="Allele Frequency & LD Scores")
