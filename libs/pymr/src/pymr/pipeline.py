"""High-level MR analysis pipeline with constant memory usage.

Orchestrates the full two-sample MR workflow:
overlap detection → load only matching SNPs → harmonize → MR analysis → sensitivity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
import zarr

from pymr.harmonization import HarmoniseResult, harmonize
from pymr.mr_analysis import MRResult, run_mr, single_snp_mr
from pymr.overlap import OverlapResult, find_overlapping_snps
from pymr.sensitivity import mr_sensitivity_summary


@dataclass
class MRPipelineResult:
    """Complete MR pipeline result."""

    overlap: OverlapResult
    harmonise: HarmoniseResult
    mr_results: list[MRResult]
    single_snp: pd.DataFrame
    sensitivity: dict[str, Any]
    exposure_path: str
    outcome_path: str

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "MR Pipeline Summary",
            "=" * 60,
            f"Exposure: {self.exposure_path}",
            f"  Total variants: {self.overlap.n_exposure_total:,}",
            f"Outcome: {self.outcome_path}",
            f"  Total variants: {self.overlap.n_outcome_total:,}",
            f"",
            f"Overlap: {self.overlap.n_common:,} SNPs",
            f"Harmonised: {self.harmonise.n_snps:,} SNPs",
            f"Alignment rate: {self.harmonise.alignment_rate:.1%}",
            "",
            "Main Analysis:",
        ]
        for r in self.mr_results:
            sig = "***" if r.pval < 0.001 else ("**" if r.pval < 0.01 else ("*" if r.pval < 0.05 else ""))
            lines.append(f"  {r.method:20s}: b={r.b:8.4f}, SE={r.se:8.4f}, P={r.pval:.2e} {sig}")

        het = self.sensitivity.get("heterogeneity", [])
        if het:
            lines.append("")
            lines.append("Heterogeneity:")
            for h in het:
                lines.append(f"  {h.method}: Q_P={h.Q_pval:.2e}")

        ei = self.sensitivity.get("egger_intercept")
        if ei:
            pleio = "DETECTED" if ei.pval < 0.05 else "not detected"
            lines.append(f"\nPleiotropy (Egger): {pleio} (P={ei.pval:.4f})")

        pr = self.sensitivity.get("mr_presso")
        if pr:
            lines.append(f"MR-PRESSO: Global P={pr.global_pval:.4f}, Outliers={pr.n_outliers}")

        lines.append(f"\nWeak IVs (F<10): {self.sensitivity.get('weak_iv_count', '?')}")
        return "\n".join(lines)


def _resolve_zarr_path(study_dir: str | Path) -> Path:
    import os
    study_dir = Path(study_dir)
    for name in os.listdir(study_dir):
        if name.endswith(".zarr"):
            return study_dir / name
    raise FileNotFoundError(f"No .zarr directory found in {study_dir}")


def _load_overlap_data(
    zarr_path: Path,
    indices: np.ndarray,
) -> pd.DataFrame:
    """Load only the specified variant indices from a zarr store."""
    z = zarr.open(str(zarr_path), mode="r")
    cols = ["id", "ref", "alt", "effect_size", "standard_error", "eaf", "log_pvalue"]
    df = pd.DataFrame({k: z[k][indices] for k in cols})
    return df


def mr_pipeline(
    exposure_path: str | Path,
    outcome_path: str | Path,
    *,
    methods: list[str] | None = None,
    action: int = 2,
    maf_threshold: float = 0.42,
    eaf_diff_threshold: float = 0.2,
    sample_size: float | None = None,
    overlap_chunk_size: int = 500_000,
    max_snps: int | None = None,
) -> MRPipelineResult:
    """Full MR analysis pipeline with constant memory usage.

    Only loads overlapping SNP data into memory. Suitable for GWAS datasets
    with millions of variants.

    Parameters
    ----------
    exposure_path : str | Path
        Path to exposure GWAS directory (containing ``*.zarr``).
    outcome_path : str | Path
        Path to outcome GWAS directory (containing ``*.zarr``).
    methods : list of str, optional
        MR methods: ``"ivw"``, ``"egger"``, ``"weighted_median"``, ``"simple_mode"``.
    action : int
        Palindromic SNP handling. 2 = remove (recommended).
    maf_threshold : float
        MAF threshold for palindromic removal.
    eaf_diff_threshold : float
        EAF difference threshold.
    sample_size : float, optional
        Sample size for F-statistic calculation.
    overlap_chunk_size : int
        Chunk size for overlap detection.
    max_snps : int, optional
        If set, pre-filter exposure to top N SNPs by p-value before overlap.
        Dramatically reduces memory usage (~100 MB vs ~2 GB).

    Returns
    -------
    MRPipelineResult
    """
    exposure_path = str(exposure_path)
    outcome_path = str(outcome_path)

    # Step 1: Find overlapping SNPs (chunked, memory-efficient)
    overlap = find_overlapping_snps(
        exposure_path,
        outcome_path,
        chunk_size=overlap_chunk_size,
        max_snps=max_snps,
    )

    if overlap.n_common == 0:
        raise ValueError("No overlapping SNPs found between exposure and outcome.")

    # Step 2: Load only overlapping data from zarr
    exp_zarr_path = _resolve_zarr_path(exposure_path)
    out_zarr_path = _resolve_zarr_path(outcome_path)

    exp_df = _load_overlap_data(exp_zarr_path, overlap.exposure_indices)
    out_df = _load_overlap_data(out_zarr_path, overlap.outcome_indices)

    # Step 3: Harmonize (small DataFrames, fits in memory)
    harm_result = harmonize(
        exp_df,
        out_df,
        action=action,
        maf_threshold=maf_threshold,
        eaf_diff_threshold=eaf_diff_threshold,
    )
    del exp_df, out_df  # free raw data

    # Step 4: MR analysis
    mr_results = run_mr(harm_result.data, methods=methods)
    snp_results = single_snp_mr(harm_result.data)

    # Step 5: Sensitivity analysis
    sensitivity = mr_sensitivity_summary(harm_result.data, mr_results, n=sample_size)

    return MRPipelineResult(
        overlap=overlap,
        harmonise=harm_result,
        mr_results=mr_results,
        single_snp=snp_results,
        sensitivity=sensitivity,
        exposure_path=exposure_path,
        outcome_path=outcome_path,
    )
