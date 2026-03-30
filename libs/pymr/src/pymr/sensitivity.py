"""Sensitivity analysis for Mendelian Randomization.

Includes heterogeneity tests, pleiotropy tests, leave-one-out analysis,
MR-PRESSO, F-statistic calculation, and R² assessment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class HeterogeneityResult:
    """Cochran's Q heterogeneity test result."""

    method: str
    Q: float
    Q_df: float
    Q_pval: float


@dataclass
class EggerInterceptResult:
    """MR-Egger intercept test for directional pleiotropy."""

    egger_intercept: float
    se: float
    pval: float


@dataclass
class LeaveOneOutResult:
    """Leave-one-out analysis result."""

    SNP: str
    b: float
    se: float
    pval: float
    ci_low: float
    ci_up: float


@dataclass
class PRESSOResult:
    """MR-PRESSO global test and outlier detection result."""

    global_Q: float
    global_Q_df: float
    global_pval: float
    n_outliers: int
    outlier_snps: list[str]
    corrected_b: float | None = None
    corrected_se: float | None = None
    corrected_pval: float | None = None


@dataclass
class FStatisticResult:
    """Instrument strength (F-statistic) result."""

    snp: str
    beta: float
    se: float
    eaf: float
    n: float
    R2: float
    F: float


def heterogeneity_test(
    data: pd.DataFrame,
    methods: list[str] | None = None,
) -> list[HeterogeneityResult]:
    """Cochran's Q test for heterogeneity across MR methods.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.
    methods : list of str
        Methods to test. Options: "ivw", "egger". Default: both.

    Returns
    -------
    list of HeterogeneityResult
    """
    if methods is None:
        methods = ["ivw", "egger"]

    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)

    valid = np.isfinite(bx) & np.isfinite(by) & (sx > 0) & (sy > 0) & (bx != 0)
    bx = bx[valid]
    by = by[valid]
    sx = sx[valid]
    sy = sy[valid]

    nsnp = len(bx)
    results: list[HeterogeneityResult] = []

    for method in methods:
        if method == "ivw":
            # IVW weights: 1 / (se_out^2 + beta_exp^2 * se_exp^2)
            w = 1.0 / (sy**2 + bx**2 * sx**2)
            wald = by / bx
            b_ivw = np.sum(w * wald) / np.sum(w)
            Q = float(np.sum(w * (wald - b_ivw) ** 2))
            Q_df = float(nsnp - 1)

        elif method == "egger":
            # MR-Egger residuals
            w = 1.0 / (sy**2 + bx**2 * sx**2)
            W = np.sum(w)
            Wx = np.sum(w * bx)
            Wy = np.sum(w * by)
            Wxx = np.sum(w * bx**2)
            Wxy = np.sum(w * bx * by)
            denom = W * Wxx - Wx**2
            if denom == 0:
                continue
            slope = (W * Wxy - Wx * Wy) / denom
            intercept = (Wy * Wxx - Wx * Wxy) / denom
            residuals = by - intercept - slope * bx
            sigma2 = np.sum(w * residuals**2) / (nsnp - 2)
            Q = float(sigma2 * (nsnp - 2))
            Q_df = float(nsnp - 2)

        else:
            raise ValueError(f"Unknown method: {method}")

        Q_pval = float(1 - stats.chi2.cdf(Q, Q_df))
        method_name = "IVW" if method == "ivw" else "MR Egger"
        results.append(HeterogeneityResult(method_name, Q, Q_df, Q_pval))

    return results


def egger_intercept_test(data: pd.DataFrame) -> EggerInterceptResult:
    """Test for directional pleiotropy using MR-Egger intercept.

    A significant intercept (p < 0.05) suggests directional pleiotropy.
    """
    from pymr.mr_analysis import mr_egger

    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)

    result = mr_egger(bx, by, sx, sy)
    intercept = result.egger_intercept
    se = result.egger_intercept_se
    pval = result.egger_intercept_pval

    return EggerInterceptResult(float(intercept), float(se), float(pval))


def leave_one_out(
    data: pd.DataFrame,
    method: str = "ivw",
) -> list[LeaveOneOutResult]:
    """Leave-one-out sensitivity analysis.

    Iteratively removes each SNP and re-runs the MR analysis.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.
    method : str
        MR method to use. Options: "ivw", "egger". Default: "ivw".

    Returns
    -------
    list of LeaveOneOutResult
    """
    from pymr.mr_analysis import mr_egger, mr_ivw

    results: list[LeaveOneOutResult] = []

    for i in range(len(data)):
        left_out = data.drop(data.index[i]).reset_index(drop=True)
        bx = left_out["beta.exposure"].values.astype(float)
        by = left_out["beta.outcome"].values.astype(float)
        sx = left_out["se.exposure"].values.astype(float)
        sy = left_out["se.outcome"].values.astype(float)

        if method == "ivw":
            r = mr_ivw(bx, by, sx, sy)
        elif method == "egger":
            r = mr_egger(bx, by, sx, sy)
        else:
            raise ValueError(f"Unknown method: {method}")

        results.append(LeaveOneOutResult(
            SNP=data.iloc[i]["SNP"],
            b=r.b, se=r.se, pval=r.pval,
            ci_low=r.ci_low, ci_up=r.ci_up,
        ))

    return results


def mr_presso(
    data: pd.DataFrame,
    nb_distribution: int = 1000,
    significance_threshold: float = 0.05,
) -> PRESSOResult:
    """MR-PRESSO: Mendelian Randomization Pleiotropy RESidual Sum and Outlier test.

    Performs global test for horizontal pleiotropy and identifies outlier SNPs.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.
    nb_distribution : int
        Number of bootstrap iterations for significance testing.
    significance_threshold : float
        P-value threshold for outlier detection.

    Returns
    -------
    PRESSOResult
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)

    valid = np.isfinite(bx) & np.isfinite(by) & (sx > 0) & (sy > 0) & (bx != 0)
    bx = bx[valid]
    by = by[valid]
    sx = sx[valid]
    sy = sy[valid]
    snps = data["SNP"].values[valid]

    nsnp = len(bx)

    # Observed IVW
    w = 1.0 / (sy**2 + bx**2 * sx**2)
    wald = by / bx
    b_obs = np.sum(w * wald) / np.sum(w)

    # Global observed RSS
    residuals_obs = wald - b_obs
    rss_obs = np.sum(w * residuals_obs**2)
    Q_obs = float(rss_obs)

    # Bootstrap RSS distribution
    rng = np.random.default_rng(42)
    rss_dist = np.empty(nb_distribution)

    for i in range(nb_distribution):
        idx = rng.integers(0, nsnp, size=nsnp)
        bw = w[idx]
        bwald = wald[idx]
        bb = np.sum(bw * bwald) / np.sum(bw)
        br = bwald - bb
        rss_dist[i] = np.sum(bw * br**2)

    # Global p-value
    global_pval = float(np.mean(rss_dist >= rss_obs))

    # Outlier detection
    # Expected residual for each SNP under null (no pleiotropy)
    expected_wald = b_obs
    snp_residuals = wald - expected_wald
    # Approximate SE of each residual
    snp_se = np.sqrt(1.0 / w)

    # Outlier: |residual| / SE > threshold (Bonferroni-adjusted)
    # Use a simpler approach: identify SNPs with extreme RSS contributions
    snp_rss = w * snp_residuals**2
    total_rss = np.sum(snp_rss)
    snp_rss_frac = snp_rss / total_rss
    expected_frac = 1.0 / nsnp

    # Outlier threshold: SNPs contributing disproportionately to RSS
    # Use MAD-based approach
    median_frac = np.median(snp_rss_frac)
    mad = np.median(np.abs(snp_rss_frac - median_frac))
    outlier_threshold = median_frac + 3.0 * 1.4826 * mad  # 3 MAD

    outlier_mask = snp_rss_frac > outlier_threshold
    outlier_snps = [str(s) for s in snps[outlier_mask]]
    n_outliers = int(outlier_mask.sum())

    # Corrected estimate (removing outliers)
    if n_outliers > 0 and n_outliers < nsnp:
        keep = ~outlier_mask
        bw = w[keep]
        bwald = wald[keep]
        b_corr = float(np.sum(bw * bwald) / np.sum(bw))
        se_corr = float(np.sqrt(1.0 / np.sum(bw)))
        z = b_corr / se_corr
        pval_corr = float(2 * stats.norm.sf(abs(z)))
    else:
        b_corr = None
        se_corr = None
        pval_corr = None

    return PRESSOResult(
        global_Q=Q_obs,
        global_Q_df=float(nsnp - 1),
        global_pval=global_pval,
        n_outliers=n_outliers,
        outlier_snps=outlier_snps,
        corrected_b=b_corr,
        corrected_se=se_corr,
        corrected_pval=pval_corr,
    )


def calculate_f_statistics(
    data: pd.DataFrame,
    n: float | None = None,
    prevalence: float | None = None,
) -> list[FStatisticResult]:
    """Calculate F-statistics and R² for each instrument.

    When N is provided: R² = 2 * beta² * eaf * (1 - eaf), F = R²*(N-2)/(1-R²)
    When N is not provided: F = (beta / se)² (Wald F-statistic per SNP)

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.
    n : float, optional
        Total sample size. If provided, uses R²-based F calculation.
    prevalence : float, optional
        Disease prevalence for case-control R² correction.

    Returns
    -------
    list of FStatisticResult
    """
    results: list[FStatisticResult] = []

    for _, row in data.iterrows():
        beta = float(row["beta.exposure"])
        se = float(row["se.exposure"])
        eaf = float(row["eaf.exposure"])

        if pd.isna(eaf) or se == 0:
            continue

        # R² for continuous trait
        R2 = 2 * beta**2 * eaf * (1 - eaf)

        if n is not None and n > 2:
            # Proper F-statistic using sample size
            if R2 < 1:
                F = R2 * (n - 2) / (1 - R2)
            else:
                F = (beta / se) ** 2
        else:
            # Wald F-statistic (per-SNP instrument strength)
            F = (beta / se) ** 2

        results.append(FStatisticResult(
            snp=str(row["SNP"]),
            beta=beta,
            se=se,
            eaf=eaf,
            n=float(n) if n else float("nan"),
            R2=float(R2),
            F=float(F),
        ))

    return results


def mr_sensitivity_summary(
    data: pd.DataFrame,
    mr_results: list,
    n: float | None = None,
) -> dict:
    """Run a comprehensive sensitivity analysis suite.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.
    mr_results : list
        Results from run_mr().
    n : float, optional
        Sample size for F-statistic calculation.

    Returns
    -------
    dict with all sensitivity analysis results.
    """
    # Heterogeneity
    het = heterogeneity_test(data)

    # Egger intercept
    try:
        egger_int = egger_intercept_test(data)
    except Exception:
        egger_int = None

    # F-statistics
    f_stats = calculate_f_statistics(data, n=n)
    f_values = [f.F for f in f_stats if np.isfinite(f.F)]
    min_f = float(np.min(f_values)) if f_values else np.nan
    mean_f = float(np.mean(f_values)) if f_values else np.nan
    weak_iv_count = sum(1 for fv in f_values if fv < 10)

    # MR-PRESSO
    try:
        presso = mr_presso(data)
    except Exception:
        presso = None

    return {
        "heterogeneity": het,
        "egger_intercept": egger_int,
        "f_statistics": f_stats,
        "min_F": min_f,
        "mean_F": mean_f,
        "weak_iv_count": weak_iv_count,
        "total_ivs": len(f_stats),
        "mr_presso": presso,
    }
