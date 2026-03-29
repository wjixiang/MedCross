from __future__ import annotations

import typer
from rich.console import Console

import pandas as pd
from lib.gwas_api_client import _to_df, get_client
from lib.output import print_error, print_json, print_table

app = typer.Typer(help="LD operations (clumping, matrix, reference lookup)")
console = Console()

_json = typer.Option(False, "--json", help="Output as JSON")


@app.command("clump")
def clump(
    rsids: list[str] = typer.Argument(help="rs IDs to clump"),
    pvals: list[float] = typer.Option([], "--pval", "-p", help="P-values for each rsid (must match count and order)"),
    pthresh: float = typer.Option(5e-8, "--pthresh", help="P-value threshold for index SNPs"),
    r2: float = typer.Option(0.001, "--r2", help="LD r2 threshold"),
    kb: int = typer.Option(5000, "--kb", help="Clumping window size (kb)"),
    pop: str = typer.Option("EUR", "--pop", help="Reference population"),
    json_output: bool = _json,
):
    """Perform LD clumping on a set of SNPs.

    Each rsid must have a corresponding --pval value (same count and order).
    Uses 1000 Genomes reference (MAF > 0.01, SNPs only).

    Example: opengwas ld clump rs1205 rs234 -p 1e-8 1e-5
    """
    if pvals and len(pvals) != len(rsids):
        print_error(f"--pval count ({len(pvals)}) must match rsid count ({len(rsids)}).")
        raise typer.Exit(1)
    client = get_client()
    try:
        result = client.ld_clump(
            rsid=rsids,
            pval=pvals or None,
            pthresh=pthresh,
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
    if json_output:
        print_json(df)
    else:
        print_table(df, title="LD Clumping Results")


@app.command("matrix")
def matrix(
    rsids: list[str] = typer.Argument(help="rs IDs for LD matrix"),
    pop: str = typer.Option("EUR", "--pop", help="Reference population"),
    json_output: bool = _json,
):
    """Get pairwise LD R values for a list of SNPs.

    Uses 1000 Genomes reference (MAF > 0.01, SNPs only).
    """
    client = get_client()
    try:
        result = client.ld_matrix(rsids, pop=pop)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    if json_output:
        print_json(result)
        return

    # LD matrix 返回 {"snplist": [...], "matrix": [[...]]}
    if isinstance(result, dict) and "snplist" in result and "matrix" in result:
        snps = result["snplist"]
        matrix = result["matrix"]
        df = pd.DataFrame(matrix, index=snps, columns=snps)
        df = df.astype(float)
        console.print(df.to_string(float_format=lambda x: f"{x:.4f}"))
        return

    df = _to_df(result)
    print_table(df, title="LD Matrix")


@app.command("reflookup")
def reflookup(
    rsids: list[str] = typer.Argument(help="rs IDs to check"),
    pop: str = typer.Option("EUR", "--pop", help="Reference population"),
    json_output: bool = _json,
):
    """Check if rsids are present in the LD reference panel."""
    client = get_client()
    try:
        result = client.ld_ref_lookup(rsids, pop=pop)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
    finally:
        client.close()

    df = _to_df(result)
    if json_output:
        print_json(df)
    else:
        print_table(df, title="LD Reference Panel Lookup")
