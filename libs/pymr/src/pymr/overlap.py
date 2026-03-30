"""Memory-efficient SNP overlap detection between zarr stores.

Supports two modes:
1. Full overlap: find all common SNPs (builds set from smaller dataset)
2. Significance-filtered (max_snps): pre-filter exposure by p-value,
   build set from only the filtered SNPs (~50 MB vs ~2 GB)
"""

from __future__ import annotations

import gc
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import zarr


@dataclass
class OverlapResult:
    """Result of SNP overlap detection between two zarr stores."""

    common_snp_ids: np.ndarray
    exposure_indices: np.ndarray
    outcome_indices: np.ndarray
    n_exposure_total: int
    n_outcome_total: int
    n_exposure_rsid: int
    n_outcome_rsid: int
    n_common: int


def _resolve_zarr_path(study_dir: str | Path) -> Path:
    study_dir = Path(study_dir)
    for name in os.listdir(study_dir):
        if name.endswith(".zarr"):
            return study_dir / name
    raise FileNotFoundError(f"No .zarr directory found in {study_dir}")


def _find_pvalue_threshold(
    log_p: zarr.Array,
    max_snps: int,
    chunk_size: int,
) -> float:
    """Find the log_pvalue threshold that keeps top N SNPs.

    Uses a max-heap approach: maintain the N-th smallest value seen so far.
    Memory: O(max_snps) floats (~4 MB for 500K).
    """
    import heapq

    # max_heap stores the LARGEST values among the smallest max_snps seen
    # We want the max_snps-th smallest, which is the max of our kept values
    heap: list[float] = []
    count = 0

    for start in range(0, log_p.shape[0], chunk_size):
        end = min(start + chunk_size, log_p.shape[0])
        chunk = log_p[start:end].astype(np.float64)
        valid = chunk[np.isfinite(chunk)]
        if len(valid) == 0:
            continue

        for v in valid:
            count += 1
            if len(heap) < max_snps:
                # Fill up: push as negative for max-heap behavior
                heapq.heappush(heap, -v)
            elif v < -heap[0]:
                # v is smaller than the current largest in our top-N
                heapq.heapreplace(heap, -v)

    if len(heap) < max_snps:
        return float("inf")

    # The threshold is the largest value in our top-N = -heap[0]
    return float(-heap[0])


def find_overlapping_snps(
    exposure_path: str | Path,
    outcome_path: str | Path,
    *,
    chunk_size: int = 500_000,
    require_rsid: bool = True,
    max_snps: int | None = None,
) -> OverlapResult:
    """Find overlapping SNP IDs between two zarr stores.

    Parameters
    ----------
    exposure_path, outcome_path : str | Path
        Paths to GWAS directories containing ``*.zarr``.
    chunk_size : int
        Variants per chunk when scanning.
    require_rsid : bool
        Only consider SNPs with IDs starting with ``rs``.
    max_snps : int, optional
        Pre-filter exposure to top N SNPs by p-value. Reduces memory
        from ~2 GB to ~100 MB.

    Returns
    -------
    OverlapResult
    """
    exp_zp = _resolve_zarr_path(exposure_path)
    out_zp = _resolve_zarr_path(outcome_path)
    exp_z = zarr.open(str(exp_zp), mode="r")
    out_z = zarr.open(str(out_zp), mode="r")
    exp_id = exp_z["id"]
    out_id = out_z["id"]
    n_exp = exp_id.shape[0]
    n_out = out_id.shape[0]

    if max_snps is not None and "log_pvalue" in exp_z:
        return _find_overlap_filtered(
            exp_z, out_z, max_snps, chunk_size, require_rsid,
            n_exp, n_out,
        )
    else:
        return _find_overlap_full(
            exp_id, out_id, chunk_size, require_rsid,
            n_exp, n_out,
        )


def _find_overlap_filtered(
    exp_z: zarr.Group,
    out_z: zarr.Group,
    max_snps: int,
    chunk_size: int,
    require_rsid: bool,
    n_exp: int,
    n_out: int,
) -> OverlapResult:
    """Filtered overlap: pre-select top N exposure SNPs by p-value."""
    log_p = exp_z["log_pvalue"]
    exp_id = exp_z["id"]
    out_id = out_z["id"]

    # Step 1: Find p-value threshold
    threshold = _find_pvalue_threshold(log_p, max_snps, chunk_size)

    # Step 2: Collect filtered exposure SNPs → build set
    exp_rsid_map: dict[str, int] = {}
    n_exp_rsid = 0

    for start in range(0, n_exp, chunk_size):
        end = min(start + chunk_size, n_exp)
        id_chunk = exp_id[start:end]
        lp_chunk = log_p[start:end].astype(np.float64)

        # Vectorized filtering
        strs = np.array(id_chunk, dtype=str)
        if require_rsid:
            rsid_mask = np.char.startswith(strs, "rs")
            strs = strs[rsid_mask]
            lp_chunk = lp_chunk[rsid_mask]
            chunk_indices = np.arange(start, end, dtype=np.int64)[rsid_mask]
        else:
            chunk_indices = np.arange(start, end, dtype=np.int64)

        pval_mask = np.isfinite(lp_chunk) & (lp_chunk <= threshold)
        if pval_mask.any():
            filtered_strs = strs[pval_mask]
            filtered_indices = chunk_indices[pval_mask]
            for k, v in zip(filtered_strs, filtered_indices):
                exp_rsid_map[str(k)] = int(v)
            n_exp_rsid += int(pval_mask.sum())

    # Step 3: Probe outcome dataset
    n_out_rsid = 0
    exp_indices: list[int] = []
    out_indices: list[int] = []
    common_rsids: list[str] = []

    for start in range(0, n_out, chunk_size):
        end = min(start + chunk_size, n_out)
        id_chunk = out_id[start:end]
        strs = np.array(id_chunk, dtype=str)

        if require_rsid:
            rsid_mask = np.char.startswith(strs, "rs")
            strs = strs[rsid_mask]
            chunk_indices = np.arange(start, end, dtype=np.int64)[rsid_mask]
        else:
            chunk_indices = np.arange(start, end, dtype=np.int64)

        n_out_rsid += len(strs)

        for k, large_idx in zip(strs, chunk_indices):
            s = str(k)
            if s in exp_rsid_map:
                exp_indices.append(exp_rsid_map[s])
                out_indices.append(int(large_idx))
                common_rsids.append(s)

    del exp_rsid_map
    gc.collect()

    exp_idx_arr = np.array(exp_indices, dtype=np.int64)
    out_idx_arr = np.array(out_indices, dtype=np.int64)
    sort_order = np.argsort(exp_idx_arr)
    exp_idx_arr = exp_idx_arr[sort_order]
    out_idx_arr = out_idx_arr[sort_order]

    return OverlapResult(
        common_snp_ids=np.array(common_rsids),
        exposure_indices=exp_idx_arr,
        outcome_indices=out_idx_arr,
        n_exposure_total=n_exp,
        n_outcome_total=n_out,
        n_exposure_rsid=n_exp_rsid,
        n_outcome_rsid=n_out_rsid,
        n_common=len(common_rsids),
    )


def _find_overlap_full(
    exp_id: zarr.Array,
    out_id: zarr.Array,
    chunk_size: int,
    require_rsid: bool,
    n_exp: int,
    n_out: int,
) -> OverlapResult:
    """Full overlap: build set from smaller dataset, probe with larger."""
    if n_exp <= n_out:
        small_id, large_id = exp_id, out_id
        small_n, large_n = n_exp, n_out
        swapped = False
    else:
        small_id, large_id = out_id, exp_id
        small_n, large_n = n_out, n_exp
        swapped = True

    rsid_map: dict[str, int] = {}
    n_small_rsid = 0

    for start in range(0, small_n, chunk_size):
        end = min(start + chunk_size, small_n)
        strs = np.array(small_id[start:end], dtype=str)
        if require_rsid:
            mask = np.char.startswith(strs, "rs")
            strs = strs[mask]
            indices = np.arange(start, end, dtype=np.int64)[mask]
        else:
            indices = np.arange(start, end, dtype=np.int64)
        for k, v in zip(strs, indices):
            rsid_map[str(k)] = int(v)
            n_small_rsid += 1

    n_large_rsid = 0
    exp_indices: list[int] = []
    out_indices: list[int] = []
    common_rsids: list[str] = []

    for start in range(0, large_n, chunk_size):
        end = min(start + chunk_size, large_n)
        strs = np.array(large_id[start:end], dtype=str)
        if require_rsid:
            mask = np.char.startswith(strs, "rs")
            strs = strs[mask]
            indices = np.arange(start, end, dtype=np.int64)[mask]
        else:
            indices = np.arange(start, end, dtype=np.int64)
        n_large_rsid += len(strs)

        for k, large_idx in zip(strs, indices):
            s = str(k)
            if s in rsid_map:
                small_idx = rsid_map[s]
                if swapped:
                    out_indices.append(small_idx)
                    exp_indices.append(int(large_idx))
                else:
                    exp_indices.append(small_idx)
                    out_indices.append(int(large_idx))
                common_rsids.append(s)

    del rsid_map
    gc.collect()

    exp_idx_arr = np.array(exp_indices, dtype=np.int64)
    out_idx_arr = np.array(out_indices, dtype=np.int64)
    sort_order = np.argsort(exp_idx_arr)
    exp_idx_arr = exp_idx_arr[sort_order]
    out_idx_arr = out_idx_arr[sort_order]

    return OverlapResult(
        common_snp_ids=np.array(common_rsids),
        exposure_indices=exp_idx_arr,
        outcome_indices=out_idx_arr,
        n_exposure_total=n_exp,
        n_outcome_total=n_out,
        n_exposure_rsid=n_small_rsid if not swapped else n_large_rsid,
        n_outcome_rsid=n_large_rsid if not swapped else n_small_rsid,
        n_common=len(common_rsids),
    )
