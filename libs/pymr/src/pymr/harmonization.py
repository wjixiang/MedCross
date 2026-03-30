"""Mendelian Randomization data harmonisation.

Ensures exposure and outcome data have consistent allele directions,
comparable beta values, and correct causal effect signs.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

# Palindromic SNP pairs (A/T and G/C) — ambiguous strand
_PALINDROMIC_PAIRS: set[frozenset[str]] = {
    frozenset({"A", "T"}),
    frozenset({"G", "C"}),
}

_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}


def _to_dataframe(dat: Any) -> pd.DataFrame:
    """Convert xarray Dataset to pandas DataFrame for MR analysis."""
    if isinstance(dat, pd.DataFrame):
        return dat.copy()
    import xarray as xr

    if isinstance(dat, xr.Dataset):
        df = dat.to_dataframe()
        df.reset_index(inplace=True)
        return df
    raise TypeError(f"Unsupported data type: {type(dat)}")


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to standard MR column names.

    Expected input columns (from OpenGWAS VCF):
        id, ref, alt, effect_size, standard_error, eaf, chrom, pos, log_pvalue

    Output columns:
        SNP, ref_allele, alt_allele, beta, se, eaf, chrom, pos, log_pval
    """
    col_map = {
        "id": "SNP",
        "ref": "ref_allele",
        "alt": "alt_allele",
        "effect_size": "beta",
        "standard_error": "se",
        "eaf": "eaf",
        "chrom": "chrom",
        "pos": "pos",
        "log_pvalue": "log_pval",
    }
    out = df.rename(columns=col_map)
    # Derive pval from log_pval if present
    if "log_pval" in out.columns and "pval" not in out.columns:
        out["pval"] = 10.0 ** (-out["log_pval"])
    return out


def _clean_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Remove SNPs with missing critical fields."""
    required = ["SNP", "beta", "se"]
    before = len(df)
    df = df.dropna(subset=required)
    after = len(df)
    if before - after > 0:
        warnings.warn(
            f"Removed {before - after} SNPs with missing beta/se values.",
            stacklevel=3,
        )
    return df


def _remove_duplicate_snps(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate SNP IDs, keeping the one with smallest p-value."""
    before = len(df)
    if "pval" in df.columns:
        df = df.sort_values("pval").drop_duplicates(subset="SNP", keep="first")
    else:
        df = df.drop_duplicates(subset="SNP", keep="first")
    after = len(df)
    if before - after > 0:
        warnings.warn(
            f"Removed {before - after} duplicate SNP IDs.",
            stacklevel=3,
        )
    return df


def _standardise_snps(df: pd.DataFrame) -> pd.DataFrame:
    """Remove non-rsID variants (coordinate-format IDs)."""
    before = len(df)
    df = df[df["SNP"].str.startswith("rs", na=False)].copy()
    after = len(df)
    if before - after > 0:
        warnings.warn(
            f"Removed {before - after} non-rsID variants.",
            stacklevel=3,
        )
    return df


def _is_palindromic_pair(a1: str, a2: str) -> bool:
    """Check if the allele pair is palindromic (A/T or G/C)."""
    pair = frozenset({a1.upper(), a2.upper()})
    return pair in _PALINDROMIC_PAIRS


def _align_alleles_vectorized(
    df: pd.DataFrame,
    action: int,
    maf_threshold: float,
    eaf_diff_threshold: float,
    log: list[str],
) -> pd.DataFrame:
    """Vectorised allele alignment for harmonisation.

    Sets 'action' column and flips outcome beta where needed.
    """
    n = len(df)

    # Upper-case alleles
    ea_exp = df["ref_allele_exposure"].str.upper().values
    oa_exp = df["alt_allele_exposure"].str.upper().values
    ea_out = df["ref_allele_outcome"].str.upper().values
    oa_out = df["alt_allele_outcome"].str.upper().values

    actions = np.full(n, "aligned", dtype=object)

    # --- Check for missing alleles ---
    missing_mask = pd.isna(df["ref_allele_exposure"]) | pd.isna(df["ref_allele_outcome"])
    actions[missing_mask] = "removed_missing"

    # --- Case 1: exact match ---
    exact = (ea_exp == ea_out) & (oa_exp == oa_out) & ~missing_mask
    actions[exact] = "aligned"

    # --- Case 2: swap match ---
    swap = (ea_exp == oa_out) & (oa_exp == ea_out) & ~missing_mask
    actions[swap] = "flipped"

    # --- Case 3: strand flip (complement) ---
    comp_ea = np.array([_COMPLEMENT.get(b, b) for b in ea_exp])
    comp_oa = np.array([_COMPLEMENT.get(b, b) for b in oa_exp])
    strand = (comp_ea == ea_out) & (comp_oa == oa_out) & ~exact & ~swap & ~missing_mask
    actions[strand] = "aligned"

    # --- Case 4: strand flip + swap ---
    strand_swap = (comp_ea == oa_out) & (comp_oa == ea_out) & ~exact & ~swap & ~strand & ~missing_mask
    actions[strand_swap] = "flipped"

    # --- Case 5: palindromic ---
    unhandled = ~exact & ~swap & ~strand & ~strand_swap & ~missing_mask
    if unhandled.any():
        for i in np.where(unhandled)[0]:
            if _is_palindromic_pair(ea_exp[i], oa_exp[i]):
                eaf_exp = df["eaf_exposure"].iloc[i]
                eaf_out = df["eaf_outcome"].iloc[i]
                if pd.notna(eaf_exp) and pd.notna(eaf_out):
                    if abs(eaf_exp - eaf_out) < eaf_diff_threshold:
                        actions[i] = "aligned"
                    elif abs(eaf_exp - (1 - eaf_out)) < eaf_diff_threshold:
                        actions[i] = "flipped"
                    else:
                        if action == 2:
                            maf = min(eaf_exp, 1 - eaf_exp)
                            if maf > maf_threshold:
                                actions[i] = "removed_palindromic"
                            else:
                                actions[i] = "aligned"
                        else:
                            actions[i] = "aligned"
                else:
                    actions[i] = "aligned"
            else:
                actions[i] = "removed_mismatch"

    return actions


@dataclass
class HarmoniseResult:
    """Result of MR data harmonisation."""

    data: pd.DataFrame
    log: list[str] = field(default_factory=list)
    action_counts: dict[str, int] = field(default_factory=dict)

    @property
    def n_snps(self) -> int:
        return len(self.data)

    @property
    def alignment_rate(self) -> float:
        n = len(self.data)
        if n == 0:
            return 0.0
        aligned = (self.data["action"] == "aligned").sum()
        return aligned / n

    def summary(self) -> str:
        lines = ["=" * 60, "Harmonisation Summary", "=" * 60]
        lines.append(f"Total SNPs after harmonisation: {self.n_snps}")
        lines.append(f"Alignment rate: {self.alignment_rate:.1%}")
        lines.append("")
        lines.append("Action counts:")
        for act, count in sorted(self.action_counts.items()):
            lines.append(f"  {act}: {count}")
        lines.append("")
        lines.append("Log:")
        for msg in self.log:
            lines.append(f"  {msg}")
        return "\n".join(lines)


def harmonize(
    exposure_dat: Any,
    outcome_dat: Any,
    action: int = 2,
    maf_threshold: float = 0.42,
    eaf_diff_threshold: float = 0.2,
) -> HarmoniseResult:
    """Harmonise exposure and outcome GWAS summary statistics for MR analysis.

    Parameters
    ----------
    exposure_dat : xarray.Dataset or pandas.DataFrame
        Exposure GWAS summary statistics.
    outcome_dat : xarray.Dataset or pandas.DataFrame
        Outcome GWAS summary statistics.
    action : int
        1 = try to infer palindromic SNPs by EAF, keep them
        2 = remove palindromic SNPs with MAF > threshold (recommended)
    maf_threshold : float
        MAF threshold for palindromic SNP removal (action=2).
    eaf_diff_threshold : float
        Maximum allowed absolute EAF difference between exposure and outcome.

    Returns
    -------
    HarmoniseResult
        Harmonised data with action column and metadata.
    """
    log: list[str] = []
    action_counts: dict[str, int] = {}

    # --- Convert to DataFrames ---
    exp_df = _to_dataframe(exposure_dat)
    out_df = _to_dataframe(outcome_dat)

    # --- Standardise columns ---
    exp_df = _standardise_columns(exp_df)
    out_df = _standardise_columns(out_df)

    log.append(f"Exposure SNPs: {len(exp_df)}")
    log.append(f"Outcome SNPs: {len(out_df)}")

    # --- Clean missing values ---
    exp_df = _clean_missing(exp_df)
    out_df = _clean_missing(out_df)

    # --- Standardise SNP IDs ---
    exp_df = _standardise_snps(exp_df)
    out_df = _standardise_snps(out_df)

    # --- Remove duplicate SNPs ---
    exp_df = _remove_duplicate_snps(exp_df)
    out_df = _remove_duplicate_snps(out_df)

    log.append(f"Exposure SNPs after QC: {len(exp_df)}")
    log.append(f"Outcome SNPs after QC: {len(out_df)}")

    # --- Inner merge on SNP ---
    merged = exp_df.merge(
        out_df,
        on="SNP",
        suffixes=("_exposure", "_outcome"),
        how="inner",
    )
    log.append(f"SNPs after merge: {len(merged)}")
    action_counts["merged"] = len(merged)

    if len(merged) == 0:
        log.append("WARNING: No overlapping SNPs found!")
        return HarmoniseResult(data=merged, log=log, action_counts=action_counts)

    # --- Allele alignment (vectorised) ---
    actions = _align_alleles_vectorized(
        merged, action, maf_threshold, eaf_diff_threshold, log
    )

    # --- Remove flagged SNPs ---
    remove_mask = np.isin(
        actions, ["removed_missing", "removed_mismatch", "removed_palindromic"]
    )
    n_removed = remove_mask.sum()
    if n_removed > 0:
        log.append(f"Removed {n_removed} SNPs (mismatch/palindromic/missing)")
        log.append(f"  removed_missing: {(actions == 'removed_missing').sum()}")
        log.append(f"  removed_mismatch: {(actions == 'removed_mismatch').sum()}")
        log.append(f"  removed_palindromic: {(actions == 'removed_palindromic').sum()}")

    merged = merged[~remove_mask].copy()
    actions = actions[~remove_mask]

    # --- Apply flips ---
    flip_mask = actions == "flipped"
    n_flipped = flip_mask.sum()
    if n_flipped > 0:
        log.append(f"Flipped {n_flipped} SNPs (allele direction reversed)")
        merged.loc[flip_mask, "beta_outcome"] = -merged.loc[flip_mask, "beta_outcome"]
        # Flip outcome EAF
        merged.loc[flip_mask, "eaf_outcome"] = (
            1.0 - merged.loc[flip_mask, "eaf_outcome"]
        )

    # --- Set final allele columns ---
    merged["effect_allele.exposure"] = merged["ref_allele_exposure"]
    merged["other_allele.exposure"] = merged["alt_allele_exposure"]
    merged["effect_allele.outcome"] = merged["ref_allele_outcome"]
    merged["other_allele.outcome"] = merged["alt_allele_outcome"]

    # --- EAF difference check ---
    if "eaf_exposure" in merged.columns and "eaf_outcome" in merged.columns:
        merged["eaf_diff"] = np.abs(
            merged["eaf_exposure"].values - merged["eaf_outcome"].values
        )
        high_diff = merged["eaf_diff"] > eaf_diff_threshold
        n_high = int(high_diff.sum())
        if n_high > 0:
            log.append(
                f"Flagged {n_high} SNPs with EAF diff > {eaf_diff_threshold}"
            )
        before_eaf = len(merged)
        merged = merged[~high_diff].copy()
        actions = actions[: len(merged)]
        n_eaf_removed = before_eaf - len(merged)
        if n_eaf_removed > 0:
            log.append(f"Removed {n_eaf_removed} SNPs due to EAF difference")
    else:
        merged["eaf_diff"] = np.nan

    # --- Store action ---
    merged["action"] = actions

    # --- Count actions ---
    unique_actions, counts = np.unique(actions, return_counts=True)
    for a, c in zip(unique_actions, counts):
        action_counts[str(a)] = int(c)

    log.append(f"Final harmonised SNPs: {len(merged)}")

    # --- Strand validation ---
    if len(merged) > 0:
        ea_match = (
            merged["effect_allele.exposure"].str.upper()
            == merged["effect_allele.outcome"].str.upper()
        )
        n_mismatch = int((~ea_match).sum())
        if n_mismatch > 0:
            log.append(
                f"WARNING: {n_mismatch} SNPs still have mismatched effect alleles"
            )

    # --- Build output DataFrame ---
    cols = [
        "SNP",
        "effect_allele.exposure", "other_allele.exposure",
        "beta_exposure", "se_exposure", "eaf_exposure",
        "effect_allele.outcome", "other_allele.outcome",
        "beta_outcome", "se_outcome", "eaf_outcome",
        "eaf_diff", "action",
    ]
    result = merged[cols].copy()
    result.columns = [
        "SNP",
        "effect_allele.exposure", "other_allele.exposure",
        "beta.exposure", "se.exposure", "eaf.exposure",
        "effect_allele.outcome", "other_allele.outcome",
        "beta.outcome", "se.outcome", "eaf.outcome",
        "eaf_diff", "action",
    ]

    # Sort by exposure pval if available
    if "pval_exposure" in merged.columns:
        sort_idx = np.argsort(merged["pval_exposure"].values)
        result = result.iloc[sort_idx]

    return HarmoniseResult(data=result, log=log, action_counts=action_counts)
