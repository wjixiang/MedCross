"""Core Mendelian Randomization analysis methods.

Implements IVW, MR-Egger, Weighted Median, and related estimators.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class MRResult:
    """Result from a single MR method."""

    method: str
    nsnp: int
    b: float  # causal estimate (beta/OR)
    se: float  # standard error
    pval: float  # p-value
    ci_low: float  # lower 95% CI
    ci_up: float  # upper 95% CI
    # Egger-specific fields (None for other methods)
    egger_intercept: float | None = None
    egger_intercept_se: float | None = None
    egger_intercept_pval: float | None = None

    def __repr__(self) -> str:
        return (
            f"MRResult(method={self.method!r}, nsnp={self.nsnp}, "
            f"b={self.b:.6f}, se={self.se:.6f}, p={self.pval:.2e}, "
            f"95%CI=[{self.ci_low:.6f}, {self.ci_up:.6f}])"
        )


@dataclass
class SingleSNPResult:
    """Wald ratio result for a single SNP."""

    snp: str
    b: float
    se: float
    pval: float
    ci_low: float
    ci_up: float


def wald_ratio(
    beta_exposure: float,
    beta_outcome: float,
    se_exposure: float,
    se_outcome: float,
) -> tuple[float, float, float]:
    """Compute Wald ratio: beta_outcome / beta_exposure.

    Returns (estimate, se, pval).
    """
    if beta_exposure == 0 or se_exposure == 0:
        return np.nan, np.nan, np.nan
    estimate = float(beta_outcome / beta_exposure)
    se = float(se_outcome / abs(beta_exposure))
    z = estimate / se
    pval = float(2 * stats.norm.sf(abs(z)))
    return estimate, se, pval


def mr_ivw(
    beta_exp: np.ndarray,
    beta_out: np.ndarray,
    se_exp: np.ndarray,
    se_out: np.ndarray,
) -> MRResult:
    """Inverse-Variance Weighted (IVW) MR estimator.

    Assumes all SNPs are valid instruments (no horizontal pleiotropy).
    Weight = 1 / se_outcome^2 (fixed effects) or 1 / (se_outcome^2 + beta_exp^2 * se_exp^2) (random effects).

    Uses random effects (multiplicative) by default for robustness.
    """
    # Wald ratios
    with np.errstate(divide="ignore", invalid="ignore"):
        wald = beta_out / beta_exp

    # Weights: 1 / (se_outcome^2 + beta_exp^2 * se_exp^2)
    weights = se_out**2 + beta_exp**2 * se_exp**2
    valid = (weights > 0) & np.isfinite(wald) & (beta_exp != 0)
    w = 1.0 / weights[valid]
    wald_v = wald[valid]

    nsnp = int(valid.sum())
    if nsnp < 2:
        return MRResult("IVW", nsnp, np.nan, np.nan, np.nan, np.nan, np.nan)

    # Weighted mean
    b = np.sum(w * wald_v) / np.sum(w)

    # Cochran's Q
    Q = np.sum(w * (wald_v - b) ** 2)
    Q_df = nsnp - 1

    # Multiplicative random effects adjustment
    if Q > Q_df:
        tau2 = (Q - Q_df) / (np.sum(w) - np.sum(w**2) / np.sum(w))
        w_re = 1.0 / (1.0 / w + tau2)
        b = np.sum(w_re * wald_v) / np.sum(w_re)
        se = np.sqrt(1.0 / np.sum(w_re))
    else:
        se = np.sqrt(1.0 / np.sum(w))

    z = b / se
    pval = 2 * stats.norm.sf(abs(z))
    ci_low = b - 1.96 * se
    ci_up = b + 1.96 * se

    return MRResult("IVW", nsnp, float(b), float(se), float(pval), float(ci_low), float(ci_up))


def mr_egger(
    beta_exp: np.ndarray,
    beta_out: np.ndarray,
    se_exp: np.ndarray,
    se_out: np.ndarray,
) -> MRResult:
    """MR-Egger regression estimator.

    Fits a weighted linear regression: beta_out = intercept + slope * beta_exp
    The slope is the causal estimate; the intercept tests for directional pleiotropy.

    Uses the NO Measurement Error (NOME) assumption with modified weights.
    """
    valid = np.isfinite(beta_exp) & np.isfinite(beta_out) & (se_exp > 0) & (se_out > 0)
    bx = beta_exp[valid].astype(float)
    by = beta_out[valid].astype(float)
    sx = se_exp[valid].astype(float)
    sy = se_out[valid].astype(float)

    nsnp = len(bx)
    if nsnp < 3:
        return MRResult("MR Egger", nsnp, np.nan, np.nan, np.nan, np.nan, np.nan)

    # Modified second-order weights (Bowden et al. 2016)
    # w_i = 1 / (se_outcome^2 + beta_exp^2 * se_exposure^2)
    w = 1.0 / (sy**2 + bx**2 * sx**2)

    # Weighted least squares: intercept + slope
    W = np.sum(w)
    Wx = np.sum(w * bx)
    Wy = np.sum(w * by)
    Wxx = np.sum(w * bx**2)
    Wxy = np.sum(w * bx * by)

    denom = W * Wxx - Wx**2
    if denom == 0:
        return MRResult("MR Egger", nsnp, np.nan, np.nan, np.nan, np.nan, np.nan)

    slope = (W * Wxy - Wx * Wy) / denom
    intercept = (Wy * Wxx - Wx * Wxy) / denom

    # Residual variance
    residuals = by - intercept - slope * bx
    sigma2 = np.sum(w * residuals**2) / (nsnp - 2)

    # SE of slope
    se_slope = np.sqrt(sigma2 * W / denom)
    se_intercept = np.sqrt(sigma2 * Wxx / denom)

    z = slope / se_slope
    pval = 2 * stats.norm.sf(abs(z))
    ci_low = slope - 1.96 * se_slope
    ci_up = slope + 1.96 * se_slope

    # Egger intercept test (stored as attribute)
    intercept_pval = 2 * stats.norm.sf(abs(intercept / se_intercept))

    result = MRResult(
        "MR Egger", nsnp,
        float(slope), float(se_slope), float(pval),
        float(ci_low), float(ci_up),
    )
    result.egger_intercept = float(intercept)
    result.egger_intercept_se = float(se_intercept)
    result.egger_intercept_pval = float(intercept_pval)
    return result


def mr_weighted_median(
    beta_exp: np.ndarray,
    beta_out: np.ndarray,
    se_exp: np.ndarray,
    se_out: np.ndarray,
) -> MRResult:
    """Weighted Median MR estimator.

    Provides consistent causal estimates when up to 50% of instruments
    are invalid. Each SNP contributes a weighted Wald ratio; the median
    of these (weighted by precision) is the estimate.
    """
    valid = np.isfinite(beta_exp) & np.isfinite(beta_out) & (beta_exp != 0) & (se_out > 0)
    bx = beta_exp[valid].astype(float)
    by = beta_out[valid].astype(float)
    sx = se_exp[valid].astype(float)
    sy = se_out[valid].astype(float)

    nsnp = len(bx)
    if nsnp < 3:
        return MRResult("Weighted Median", nsnp, np.nan, np.nan, np.nan, np.nan, np.nan)

    # Wald ratios and weights
    wald = by / bx
    w = 1.0 / sy**2

    # Bootstrap for SE estimation (1000 iterations)
    n_boot = 1000
    rng = np.random.default_rng(42)
    boot_estimates = np.empty(n_boot)

    for i in range(n_boot):
        idx = rng.integers(0, nsnp, size=nsnp)
        bw = w[idx]
        bwald = wald[idx]

        # Normalise weights
        bw = bw / np.sum(bw)

        # Weighted median using the sorting method
        order = np.argsort(bwald)
        sorted_wald = bwald[order]
        sorted_w = bw[order]
        cumw = np.cumsum(sorted_w)
        j = np.searchsorted(cumw, 0.5)
        boot_estimates[i] = sorted_wald[min(j, len(sorted_wald) - 1)]

    # Point estimate
    w_norm = w / np.sum(w)
    order = np.argsort(wald)
    sorted_wald = wald[order]
    sorted_w = w_norm[order]
    cumw = np.cumsum(sorted_w)
    j = np.searchsorted(cumw, 0.5)
    b = sorted_wald[min(j, len(sorted_wald) - 1)]

    se = float(np.std(boot_estimates, ddof=1))
    if se == 0:
        se = float(np.std(boot_estimates)) + 1e-10

    z = b / se
    pval = 2 * stats.norm.sf(abs(z))
    ci_low = b - 1.96 * se
    ci_up = b + 1.96 * se

    return MRResult(
        "Weighted Median", nsnp,
        float(b), float(se), float(pval),
        float(ci_low), float(ci_up),
    )


def mr_simple_mode(
    beta_exp: np.ndarray,
    beta_out: np.ndarray,
    se_out: np.ndarray,
) -> MRResult:
    """Simple mode-based MR estimator.

    Identifies the cluster of Wald ratios with the highest density (mode).
    Robust to up to 50% invalid instruments.
    """
    valid = np.isfinite(beta_exp) & np.isfinite(beta_out) & (beta_exp != 0) & (se_out > 0)
    bx = beta_exp[valid].astype(float)
    by = beta_out[valid].astype(float)
    sy = se_out[valid].astype(float)

    nsnp = len(bx)
    if nsnp < 3:
        return MRResult("Simple Mode", nsnp, np.nan, np.nan, np.nan, np.nan, np.nan)

    wald = by / bx
    w = 1.0 / sy**2

    # Weighted kernel density estimation to find mode
    # Use histogram-based approach
    n_bins = max(int(np.sqrt(nsnp)), 10)
    pct = np.percentile(wald, [1, 99])
    hist_range: tuple[float, float] = (float(pct[0]), float(pct[1]))

    if hist_range[0] == hist_range[1]:
        return MRResult("Simple Mode", nsnp, float(wald[0]), np.nan, np.nan, np.nan, np.nan)

    hist, bin_edges = np.histogram(wald, bins=n_bins, range=hist_range, weights=w)

    # Find mode bin
    mode_idx = np.argmax(hist)
    mode_low = bin_edges[mode_idx]
    mode_high = bin_edges[mode_idx + 1]
    b = (mode_low + mode_high) / 2.0

    # Bootstrap for SE
    n_boot = 1000
    rng = np.random.default_rng(42)
    boot_estimates = np.empty(n_boot)

    for i in range(n_boot):
        idx = rng.integers(0, nsnp, size=nsnp)
        bw = w[idx]
        bwald = wald[idx]
        if len(bwald) < 3:
            boot_estimates[i] = b
            continue
        bh, be = np.histogram(bwald, bins=n_bins, range=hist_range, weights=bw)
        bmi = np.argmax(bh)
        boot_estimates[i] = (be[bmi] + be[bmi + 1]) / 2.0

    se = float(np.std(boot_estimates, ddof=1))
    if se == 0:
        se = float(np.std(boot_estimates)) + 1e-10

    z = b / se
    pval = 2 * stats.norm.sf(abs(z))
    ci_low = b - 1.96 * se
    ci_up = b + 1.96 * se

    return MRResult(
        "Simple Mode", nsnp,
        float(b), float(se), float(pval),
        float(ci_low), float(ci_up),
    )


def run_mr(
    data: pd.DataFrame,
    methods: list[str] | None = None,
) -> list[MRResult]:
    """Run MR analysis using specified methods.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data with columns:
        beta.exposure, se.exposure, beta.outcome, se.outcome
    methods : list of str, optional
        Methods to use. Options: "ivw", "egger", "weighted_median", "simple_mode".
        Default: all methods.

    Returns
    -------
    list of MRResult
    """
    if methods is None:
        methods = ["ivw", "egger", "weighted_median", "simple_mode"]

    bx = np.asarray(data["beta.exposure"].values, dtype=float)
    by = np.asarray(data["beta.outcome"].values, dtype=float)
    sx = np.asarray(data["se.exposure"].values, dtype=float)
    sy = np.asarray(data["se.outcome"].values, dtype=float)

    results: list[MRResult] = []
    for method in methods:
        if method == "ivw":
            results.append(mr_ivw(bx, by, sx, sy))
        elif method == "egger":
            results.append(mr_egger(bx, by, sx, sy))
        elif method == "weighted_median":
            results.append(mr_weighted_median(bx, by, sx, sy))
        elif method == "simple_mode":
            results.append(mr_simple_mode(bx, by, sy))
        else:
            raise ValueError(f"Unknown MR method: {method}")

    return results


def single_snp_mr(data: pd.DataFrame) -> pd.DataFrame:
    """Compute Wald ratio for each individual SNP.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.

    Returns
    -------
    pd.DataFrame with columns: SNP, b, se, pval, ci_low, ci_up
    """
    records = []
    for _, row in data.iterrows():
        bx = float(row["beta.exposure"])
        by = float(row["beta.outcome"])
        sx = float(row["se.exposure"])
        sy = float(row["se.outcome"])
        b, se, pval = wald_ratio(bx, by, sx, sy)
        ci_low = b - 1.96 * se if np.isfinite(se) else np.nan
        ci_up = b + 1.96 * se if np.isfinite(se) else np.nan
        records.append({
            "SNP": row["SNP"],
            "b": b, "se": se, "pval": pval,
            "ci_low": ci_low, "ci_up": ci_up,
        })
    return pd.DataFrame(records)
