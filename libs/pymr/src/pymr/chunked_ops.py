"""Optimized MR operations using running sums.

Provides O(N) leave-one-out analysis by subtracting per-SNP contributions
from global running sums, instead of creating N copies of the DataFrame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from pymr.sensitivity import LeaveOneOutResult


def leave_one_out_ivw_fast(
    data: pd.DataFrame,
) -> list[LeaveOneOutResult]:
    """O(N) leave-one-out IVW using running sum subtraction.

    Instead of N calls to mr_ivw (each O(N)), computes all N leave-one-out
    estimates in a single pass using the global accumulated sums.

    Parameters
    ----------
    data : pd.DataFrame
        Harmonised MR data.

    Returns
    -------
    list of LeaveOneOutResult
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)
    snps = data["SNP"].values

    # Compute per-SNP values
    with np.errstate(divide="ignore", invalid="ignore"):
        wald = by / bx
    weights_denom = sy**2 + bx**2 * sx**2
    valid = (weights_denom > 0) & np.isfinite(wald) & (bx != 0)

    bx = bx[valid]
    by = by[valid]
    sx = sx[valid]
    sy = sy[valid]
    wald = wald[valid]
    snps = snps[valid]
    w = 1.0 / weights_denom[valid]

    nsnp = len(bx)
    if nsnp < 3:
        return []

    # Global sums
    global_sum_w = np.sum(w)
    global_sum_w_wald = np.sum(w * wald)
    global_sum_w_wald_sq = np.sum(w * wald**2)
    global_sum_w_sq = np.sum(w**2)

    # Global IVW estimate (fixed effects)
    b_global = global_sum_w_wald / global_sum_w

    # Global Q
    Q_global = global_sum_w_wald_sq - 2 * b_global * global_sum_w_wald + b_global**2 * global_sum_w
    Q_df = nsnp - 1

    # Tau2 for random effects
    if Q_global > Q_df:
        tau2 = (Q_global - Q_df) / (global_sum_w - global_sum_w_sq / global_sum_w)
    else:
        tau2 = 0.0

    # Per-SNP leave-one-out using sum subtraction
    results: list[LeaveOneOutResult] = []
    for i in range(nsnp):
        loo_sum_w = global_sum_w - w[i]
        loo_sum_w_wald = global_sum_w_wald - w[i] * wald[i]
        loo_sum_w_wald_sq = global_sum_w_wald_sq - w[i] * wald[i] ** 2
        loo_sum_w_sq = global_sum_w_sq - w[i] ** 2
        loo_n = nsnp - 1

        if loo_n < 2 or loo_sum_w <= 0:
            results.append(LeaveOneOutResult(
                SNP=str(snps[i]), b=np.nan, se=np.nan, pval=np.nan,
                ci_low=np.nan, ci_up=np.nan,
            ))
            continue

        b = loo_sum_w_wald / loo_sum_w

        # Leave-one-out Q
        Q_loo = loo_sum_w_wald_sq - 2 * b * loo_sum_w_wald + b**2 * loo_sum_w
        Q_df_loo = loo_n - 1

        # Random effects adjustment
        if Q_loo > Q_df_loo and loo_sum_w > 0:
            tau2_loo = (Q_loo - Q_df_loo) / (loo_sum_w - loo_sum_w_sq / loo_sum_w)
            # Approximate: sum(1/(1/w + tau2)) ≈ loo_sum_w^2 / (loo_sum_w + tau2 * loo_sum_w_sq)
            denom_re = loo_sum_w + tau2_loo * loo_sum_w_sq
            if denom_re > 0:
                se = np.sqrt(loo_sum_w / denom_re) / np.sqrt(loo_sum_w)
            else:
                se = np.sqrt(1.0 / loo_sum_w)
        else:
            se = np.sqrt(1.0 / loo_sum_w)

        z = b / se if se > 0 else 0.0
        pval = float(2 * stats.norm.sf(abs(z)))
        ci_low = b - 1.96 * se
        ci_up = b + 1.96 * se

        results.append(LeaveOneOutResult(
            SNP=str(snps[i]),
            b=float(b),
            se=float(se),
            pval=pval,
            ci_low=float(ci_low),
            ci_up=float(ci_up),
        ))

    return results
