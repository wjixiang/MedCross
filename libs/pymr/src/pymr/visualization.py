"""Visualization for Mendelian Randomization analysis using plotnine.

Implements all standard MR plots: scatter, forest, funnel,
leave-one-out, QQ, single SNP forest, and more.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from plotnine import (
    aes,
    geom_errorbarh,
    geom_errorbar,
    geom_hline,
    geom_line,
    geom_point,
    geom_vline,
    geom_abline,
    geom_text,
    geom_bar,
    ggplot,
    labs,
    scale_color_manual,
    scale_x_continuous,
    scale_y_continuous,
    scale_fill_manual,
    theme_bw,
    theme,
    element_text,
    element_blank,
    position_dodge,
)

from pymr.mr_analysis import MRResult


# ── Color palette ──────────────────────────────────────────────
_METHOD_COLORS = {
    "IVW": "#1f77b4",
    "MR Egger": "#ff7f0e",
    "Weighted Median": "#2ca02c",
    "Simple Mode": "#d62728",
}


def _method_color(method: str) -> str:
    return _METHOD_COLORS.get(method, "#333333")


# ── Scatter Plot ───────────────────────────────────────────────
def scatter_plot(
    data: pd.DataFrame,
    mr_results: list[MRResult],
    title: str = "MR Scatter Plot",
) -> ggplot:
    """MR scatter plot showing SNP effects on exposure vs outcome.

    Each point is a SNP. Lines represent different MR method fits.
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)

    df = pd.DataFrame({
        "beta.exposure": bx,
        "beta.outcome": by,
    })

    # Compute method fit lines
    lines = []
    for r in mr_results:
        if r.method == "IVW":
            lines.append({"method": "IVW", "slope": r.b, "intercept": 0.0})
        elif r.method == "MR Egger":
            intercept = getattr(r, "_egger_intercept", 0.0)
            lines.append({"method": "MR Egger", "slope": r.b, "intercept": intercept})
        elif r.method == "Weighted Median":
            lines.append({"method": "Weighted Median", "slope": r.b, "intercept": 0.0})

    if not lines:
        return None

    # Create range for regression lines
    x_range = np.linspace(np.percentile(bx, 0.5), np.percentile(bx, 99.5), 100)

    line_data = []
    for ln in lines:
        y_line = ln["intercept"] + ln["slope"] * x_range
        line_data.extend([
            {"beta.exposure": x, "beta.outcome": y, "method": ln["method"]}
            for x, y in zip(x_range, y_line)
        ])
    line_df = pd.DataFrame(line_data)

    p = (
        ggplot(df, aes(x="beta.exposure", y="beta.outcome"))
        + geom_point(color="#555555", alpha=0.3, size=1.0, shape="o")
        + geom_line(
            line_df,
            aes(color="method", linetype="method"),
            size=1.0,
        )
        + scale_color_manual(values=_METHOD_COLORS)
        + geom_hline(yintercept=0, linetype="dashed", color="grey", alpha=0.5)
        + geom_vline(xintercept=0, linetype="dashed", color="grey", alpha=0.5)
        + labs(
            x="SNP effect on exposure (beta)",
            y="SNP effect on outcome (beta)",
            title=title,
            color="Method",
            linetype="Method",
        )
        + theme_bw(base_size=12)
    )
    return p


# ── Forest Plot ────────────────────────────────────────────────
def forest_plot(
    mr_results: list[MRResult],
    title: str = "MR Forest Plot",
    x_label: str = "Causal estimate (beta)",
) -> ggplot:
    """Forest plot comparing MR method estimates.

    Shows each method's estimate with 95% CI.
    """
    df = pd.DataFrame([
        {
            "method": r.method,
            "estimate": r.b,
            "ci_low": r.ci_low,
            "ci_up": r.ci_up,
            "nsnp": r.nsnp,
        }
        for r in mr_results
        if np.isfinite(r.b)
    ])
    if df.empty:
        return None

    df["method"] = pd.Categorical(
        df["method"], categories=df["method"].tolist()[::-1], ordered=True
    )

    p = (
        ggplot(df, aes(x="estimate", y="method", color="method"))
        + geom_errorbarh(
            aes(xmin="ci_low", xmax="ci_up"),
            height=0.2,
            size=1.0,
        )
        + geom_point(size=4, shape="D")
        + geom_vline(xintercept=0, linetype="dashed", color="grey")
        + scale_color_manual(values=_METHOD_COLORS)
        + labs(
            x=x_label,
            y="",
            title=title,
        )
        + theme_bw(base_size=12)
        + theme(legend_position="none")
    )
    return p


# ── Single SNP Forest Plot ─────────────────────────────────────
def single_snp_forest(
    snp_results: pd.DataFrame,
    overall_result: MRResult | None = None,
    title: str = "Single SNP Forest Plot",
    top_n: int = 50,
) -> ggplot:
    """Forest plot showing individual SNP Wald ratio estimates.

    Parameters
    ----------
    snp_results : pd.DataFrame
        Output from single_snp_mr().
    overall_result : MRResult, optional
        Overall IVW estimate to overlay.
    top_n : int
        Number of top SNPs (by p-value) to show.
    """
    df = snp_results.dropna(subset=["b"]).copy()
    df = df.sort_values("pval").head(top_n)
    df = df.sort_values("b", ascending=True)
    df["SNP"] = pd.Categorical(df["SNP"], categories=df["SNP"].tolist(), ordered=True)

    p = (
        ggplot(df, aes(x="b", y="SNP"))
        + geom_errorbarh(aes(xmin="ci_low", xmax="ci_up"), height=0.0, size=0.5)
        + geom_point(size=2, color="#1f77b4")
        + geom_vline(xintercept=0, linetype="dashed", color="grey")
    )

    if overall_result and np.isfinite(overall_result.b):
        p = p + geom_vline(
            xintercept=overall_result.b,
            color="red",
            linetype="dashed",
            size=1.0,
        )

    p = (
        p
        + labs(x="Wald ratio (beta)", y="", title=title)
        + theme_bw(base_size=10)
        + theme(
            axis_text_y=element_text(size=6),
            legend_position="none",
        )
    )
    return p


# ── Funnel Plot ────────────────────────────────────────────────
def funnel_plot(
    data: pd.DataFrame,
    title: str = "MR Funnel Plot",
) -> ggplot:
    """Funnel plot to assess asymmetry / small study bias.

    X-axis: causal effect (beta_outcome / beta_exposure)
    Y-axis: inverse standard error (precision)
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)

    # Wald ratios and SE
    with np.errstate(divide="ignore", invalid="ignore"):
        wald = by / bx
        se_wald = sy / np.abs(bx)

    valid = np.isfinite(wald) & np.isfinite(se_wald) & (se_wald > 0)
    precision = 1.0 / se_wald[valid]

    df = pd.DataFrame({
        "estimate": wald[valid],
        "precision": precision,
    })

    # Add overall IVW estimate
    w = precision**2
    b_ivw = np.sum(w * df["estimate"].values) / np.sum(w)

    p = (
        ggplot(df, aes(x="estimate", y="precision"))
        + geom_point(alpha=0.3, color="#1f77b4", size=1.0)
        + geom_vline(xintercept=b_ivw, linetype="dashed", color="red", size=0.8)
        + geom_vline(xintercept=0, linetype="dashed", color="grey")
        + labs(
            x="Causal effect estimate (Wald ratio)",
            y="Precision (1/SE)",
            title=title,
        )
        + theme_bw(base_size=12)
    )
    return p


# ── Leave-One-Out Plot ─────────────────────────────────────────
def leave_one_out_plot(
    loo_results: list,
    overall_result: MRResult | None = None,
    title: str = "Leave-One-Out Plot",
    top_n: int = 50,
) -> ggplot:
    """Leave-one-out plot.

    X-axis: causal estimate when each SNP is removed.
    Y-axis: the removed SNP.
    """
    df = pd.DataFrame([
        {
            "SNP": r.SNP,
            "estimate": r.b,
            "ci_low": r.ci_low,
            "ci_up": r.ci_up,
            "pval": r.pval,
        }
        for r in loo_results
        if np.isfinite(r.b)
    ])
    if df.empty:
        return None

    # Sort by p-value and take top N
    df = df.sort_values("pval").head(top_n)
    df = df.sort_values("estimate", ascending=True)
    df["SNP"] = pd.Categorical(df["SNP"], categories=df["SNP"].tolist(), ordered=True)

    p = (
        ggplot(df, aes(x="estimate", y="SNP"))
        + geom_errorbarh(aes(xmin="ci_low", xmax="ci_up"), height=0.0, size=0.5)
        + geom_point(size=2, color="#2ca02c")
        + geom_vline(xintercept=0, linetype="dashed", color="grey")
    )

    if overall_result and np.isfinite(overall_result.b):
        p = p + geom_vline(
            xintercept=overall_result.b,
            color="red",
            linetype="dashed",
            size=1.0,
        )

    p = (
        p
        + labs(x="Causal estimate (beta)", y="", title=title)
        + theme_bw(base_size=10)
        + theme(
            axis_text_y=element_text(size=6),
            legend_position="none",
        )
    )
    return p


# ── QQ Plot ────────────────────────────────────────────────────
def qq_plot(
    data: pd.DataFrame,
    title: str = "QQ Plot of SNP P-values",
) -> ggplot:
    """QQ plot of single SNP MR p-values.

    Assesses inflation and deviation from expected distribution.
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)

    # Wald ratio p-values
    with np.errstate(divide="ignore", invalid="ignore"):
        wald = by / bx
        se_wald = sy / np.abs(bx)
        z = wald / se_wald

    valid = np.isfinite(z)
    from scipy import stats as sp_stats
    pvals = 2 * sp_stats.norm.sf(np.abs(z[valid]))
    pvals = np.sort(pvals)

    # Expected uniform
    n = len(pvals)
    expected = np.arange(1, n + 1) / (n + 1)

    # Lambda GC
    from scipy.stats import chi2
    chi2_obs = chi2.ppf(1 - pvals, df=1)
    lambda_gc = float(np.median(chi2_obs) / chi2.ppf(0.5, df=1))

    df = pd.DataFrame({
        "expected": -np.log10(expected),
        "observed": -np.log10(pvals),
    })

    max_val = max(df["expected"].max(), df["observed"].max()) * 1.1

    p = (
        ggplot(df, aes(x="expected", y="observed"))
        + geom_point(alpha=0.3, color="#1f77b4", size=1.0)
        + geom_abline(slope=1, intercept=0, linetype="dashed", color="grey", size=0.8)
        + labs(
            x="Expected -log10(P)",
            y="Observed -log10(P)",
            title=f"{title}\n(lambda GC = {lambda_gc:.3f})",
        )
        + scale_x_continuous(limits=(0, max_val))
        + scale_y_continuous(limits=(0, max_val))
        + theme_bw(base_size=12)
    )
    return p


# ── Heterogeneity Forest Plot ──────────────────────────────────
def heterogeneity_forest(
    data: pd.DataFrame,
    title: str = "Heterogeneity Forest Plot",
    top_n: int = 50,
) -> ggplot:
    """Plot individual SNP contribution to heterogeneity.

    Shows Wald ratio and its deviation from the IVW estimate.
    """
    bx = data["beta.exposure"].values.astype(float)
    by = data["beta.outcome"].values.astype(float)
    sx = data["se.exposure"].values.astype(float)
    sy = data["se.outcome"].values.astype(float)

    # IVW weights and estimate
    w = 1.0 / (sy**2 + bx**2 * sx**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        wald = by / bx
    valid = np.isfinite(wald) & (w > 0)
    b_ivw = np.sum(w[valid] * wald[valid]) / np.sum(w[valid])

    # Per-SNP residual
    residuals = wald[valid] - b_ivw
    # Per-SNP Cochran's Q contribution
    q_contrib = w[valid] * residuals**2
    snps = data["SNP"].values[valid]

    df = pd.DataFrame({
        "SNP": snps,
        "wald": wald[valid],
        "Q_contribution": q_contrib,
    })

    # Top contributors
    df = df.sort_values("Q_contribution", ascending=False).head(top_n)
    df = df.sort_values("Q_contribution", ascending=True)
    df["SNP"] = pd.Categorical(df["SNP"], categories=df["SNP"].tolist(), ordered=True)

    p = (
        ggplot(df, aes(x="Q_contribution", y="SNP"))
        + geom_point(size=2, color="#d62728")
        + geom_vline(xintercept=0, linetype="dashed", color="grey")
        + labs(
            x="Cochran's Q contribution",
            y="",
            title=title,
        )
        + theme_bw(base_size=10)
        + theme(
            axis_text_y=element_text(size=6),
            legend_position="none",
        )
    )
    return p


# ── Multi-exposure Heatmap ─────────────────────────────────────
def heatmap(
    mr_results_dict: dict[str, list[MRResult]],
    method: str = "IVW",
    title: str = "MR Results Heatmap",
) -> ggplot:
    """Heatmap of MR results across multiple exposure-outcome pairs.

    Parameters
    ----------
    mr_results_dict : dict
        Keys are "exposure -> outcome" labels, values are lists of MRResult.
    method : str
        Which method to display.
    """
    records = []
    for label, results in mr_results_dict.items():
        for r in results:
            if r.method == method and np.isfinite(r.b):
                records.append({
                    "pair": label,
                    "estimate": r.b,
                    "pval": r.pval,
                })
    if not records:
        return None

    df = pd.DataFrame(records)

    # Significance stars
    def sig_stars(p):
        if p < 0.001:
            return "***"
        elif p < 0.01:
            return "**"
        elif p < 0.05:
            return "*"
        return ""

    df["significance"] = df["pval"].apply(sig_stars)
    df["label"] = df["estimate"].round(3).astype(str) + df["significance"]
    df["pair"] = pd.Categorical(df["pair"], categories=df["pair"].tolist(), ordered=True)

    # Color by sign and significance
    df["color"] = np.where(
        (df["pval"] < 0.05) & (df["estimate"] > 0), "Positive*",
        np.where(
            (df["pval"] < 0.05) & (df["estimate"] < 0), "Negative*",
            "NS",
        ),
    )

    p = (
        ggplot(df, aes(x="1", y="pair", fill="color"))
        + geom_bar(stat="identity", width=0.8)
        + geom_text(aes(label="label"), color="white", size=10, fontweight="bold")
        + scale_fill_manual(
            values={"Positive*": "#d62728", "Negative*": "#1f77b4", "NS": "#cccccc"},
        )
        + labs(title=title, x="", y="")
        + theme_bw(base_size=12)
        + theme(
            axis_text_x=element_blank(),
            axis_ticks_x=element_blank(),
            legend_position="none",
        )
    )
    return p


# ── Effect Direction Consistency Plot ──────────────────────────
def direction_consistency_plot(
    mr_results: list[MRResult],
    title: str = "Method Consistency Plot",
) -> ggplot:
    """Plot showing causal effect direction and significance across methods.

    Arrows indicate direction; color indicates significance.
    """
    df = pd.DataFrame([
        {
            "method": r.method,
            "estimate": r.b,
            "se": r.se,
            "pval": r.pval,
            "sig": "Significant" if r.pval < 0.05 else "Not significant",
            "direction": "Positive" if r.b > 0 else "Negative",
        }
        for r in mr_results
        if np.isfinite(r.b)
    ])
    if df.empty:
        return None

    p = (
        ggplot(df, aes(x="method", y="estimate", fill="sig"))
        + geom_bar(stat="identity", width=0.6, position=position_dodge(width=0.8))
        + geom_errorbar(aes(ymin="estimate - se", ymax="estimate + se"), width=0.2)
        + geom_hline(yintercept=0, linetype="dashed", color="grey")
        + scale_fill_manual(values={"Significant": "#d62728", "Not significant": "#cccccc"})
        + labs(x="", y="Causal estimate (beta)", title=title, fill="Significance")
        + theme_bw(base_size=12)
        + theme(axis_text_x=element_text(angle=45, hjust=1))
    )
    return p
