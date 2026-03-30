"""GWAS summary statistics data loader.

将 OpenGWAS VCF.gz 文件转换为 Zarr 格式，并通过 xarray 高效加载。
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr
import zarr
from cyvcf2 import VCF

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# VCF 中 FORMAT 字段名到 Dataset 变量名的映射
_FORMAT_FIELD_MAP: dict[str, str] = {
    "ES": "effect_size",
    "SE": "standard_error",
    "LP": "log_pvalue",
    "AF": "eaf",
    "SS": "sample_size",
    "EZ": "z_score",
    "SI": "imputation_accuracy",
    "NC": "n_cases",
}

# 染色体名称到整数的映射（用于紧凑存储）
_CHROM_MAP: dict[str, int] = {
    **{str(i): i for i in range(1, 23)},
    "X": 23,
    "Y": 24,
    "MT": 25,
    "M": 25,
}

# Zarr 压缩配置
from zarr import codecs as _zarr_codecs  # type: ignore[import-untyped]

_NUM_COMPRESSOR = _zarr_codecs.BloscCodec(cname="lz4", clevel=5, shuffle=_zarr_codecs.BloscShuffle.bitshuffle)
_STR_COMPRESSOR = _zarr_codecs.BloscCodec(cname="zstd", clevel=3, shuffle=_zarr_codecs.BloscShuffle.noshuffle)

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StudyMetadata:
    """从 VCF ##SAMPLE 行解析的研究元信息。"""

    study_id: str
    total_variants: int
    variants_not_read: int
    harmonised_variants: int
    variants_not_harmonised: int
    switched_alleles: int
    normalised_variants: int
    total_controls: float | None
    total_cases: float | None
    study_type: str
    source_vcf: str


def _parse_sample_header(vcf: VCF, source_vcf: str) -> StudyMetadata:
    """从 VCF raw header 解析 ##SAMPLE 元信息。"""
    sample_line = None
    for line in vcf.raw_header.split("\n"):
        if line.startswith("##SAMPLE"):
            sample_line = line
            break
    if sample_line is None:
        raise ValueError("VCF header 中未找到 ##SAMPLE 行")

    # 提取 <> 内的内容，然后解析 key=value 对
    inner = re.search(r'<(.+)>$', sample_line)
    if inner is None:
        raise ValueError(f"无法解析 SAMPLE 行: {sample_line}")
    fields = re.findall(r'(\w+)=(?:"([^"]*)"|([^,\s>]+))', inner.group(1))
    kv = {k: v2 if v2 else v1 for k, v1, v2 in fields}

    return StudyMetadata(
        study_id=kv["ID"],
        total_variants=int(kv.get("TotalVariants", 0)),
        variants_not_read=int(kv.get("VariantsNotRead", 0)),
        harmonised_variants=int(kv.get("HarmonisedVariants", 0)),
        variants_not_harmonised=int(kv.get("VariantsNotHarmonised", 0)),
        switched_alleles=int(kv.get("SwitchedAlleles", 0)),
        normalised_variants=int(kv.get("NormalisedVariants", 0)),
        total_controls=float(kv["TotalControls"]) if "TotalControls" in kv else None,
        total_cases=float(kv["TotalCases"]) if "TotalCases" in kv else None,
        study_type=kv.get("StudyType", "Unknown"),
        source_vcf=source_vcf,
    )


# ---------------------------------------------------------------------------
# VCF → Zarr conversion
# ---------------------------------------------------------------------------


def _detect_format_fields(vcf: VCF) -> list[str]:
    """探测 VCF 中实际包含的 FORMAT 字段。

    VCF header 声明了 9 个 FORMAT 字段，但实际数据行可能只包含其中一部分。
    读取前 1000 个变异来确定实际存在的字段。
    """
    available = set()
    count = 0
    for var in vcf:
        for field_name in _FORMAT_FIELD_MAP:
            if field_name not in available and var.format(field_name) is not None:
                available.add(field_name)
        count += 1
        if count >= 1000:
            break
    # 按声明顺序返回
    return [f for f in _FORMAT_FIELD_MAP if f in available]


def _read_chrom_chunk(
    vcf_path: str,
    chrom: str,
    format_fields: list[str],
    chunk_size: int,
) -> list[xr.Dataset]:
    """读取单个染色体，按 chunk_size 分块返回 Dataset 列表。"""
    reader = VCF(vcf_path)
    buf_size = chunk_size
    chrom_arr = np.empty(buf_size, dtype=np.int8)
    pos_arr = np.empty(buf_size, dtype=np.int32)
    id_arr = np.empty(buf_size, dtype=object)
    ref_arr = np.empty(buf_size, dtype=object)
    alt_arr = np.empty(buf_size, dtype=object)
    info_af_arr = np.empty(buf_size, dtype=np.float32)

    fmt_arrs: dict[str, np.ndarray] = {}
    for f in format_fields:
        dtype = np.int32 if f in ("SS", "NC") else np.float32
        fmt_arrs[f] = np.empty(buf_size, dtype=dtype)

    chunks: list[xr.Dataset] = []
    idx = 0

    for var in reader(f"{chrom}:1-500000000"):
        if idx >= buf_size:
            chunks.append(_build_chunk_ds(
                chrom_arr, pos_arr, id_arr, ref_arr, alt_arr,
                info_af_arr, fmt_arrs, format_fields, idx,
            ))
            idx = 0

        chrom_arr[idx] = _CHROM_MAP.get(var.CHROM, 0)
        pos_arr[idx] = var.POS
        id_arr[idx] = var.ID if var.ID else ""
        ref_arr[idx] = var.REF
        alt_arr[idx] = var.ALT[0] if var.ALT else ""
        info_af_arr[idx] = var.INFO.get("AF") or np.nan

        for f in format_fields:
            val = var.format(f)
            fmt_arrs[f][idx] = val.flat[0] if val is not None else np.nan

        idx += 1

    reader.close()

    if idx > 0:
        chunks.append(_build_chunk_ds(
            chrom_arr, pos_arr, id_arr, ref_arr, alt_arr,
            info_af_arr, fmt_arrs, format_fields, idx,
        ))

    return chunks


def _build_chunk_ds(
    chrom_arr: np.ndarray,
    pos_arr: np.ndarray,
    id_arr: np.ndarray,
    ref_arr: np.ndarray,
    alt_arr: np.ndarray,
    info_af_arr: np.ndarray,
    fmt_arrs: dict[str, np.ndarray],
    format_fields: list[str],
    length: int,
) -> xr.Dataset:
    """从缓冲区构建单个 xarray Dataset chunk。"""
    data_vars: dict[str, tuple[str, np.ndarray]] = {
        "info_af": ("variant", info_af_arr[:length].copy()),
    }
    for f in format_fields:
        data_vars[_FORMAT_FIELD_MAP[f]] = ("variant", fmt_arrs[f][:length].copy())

    # 使用固定长度 Unicode 字符串，确保所有 chunk 的 dtype 一致
    # rsID 最长约 30 字符，等位基因最长约 200 字符（罕见 indel）
    _STR_DTYPE = np.dtype("U256")

    coords: dict[str, tuple[str, np.ndarray]] = {
        "chrom": ("variant", chrom_arr[:length].copy()),
        "pos": ("variant", pos_arr[:length].copy()),
        "id": ("variant", np.array(id_arr[:length], dtype=_STR_DTYPE)),
        "ref": ("variant", np.array(ref_arr[:length], dtype=_STR_DTYPE)),
        "alt": ("variant", np.array(alt_arr[:length], dtype=_STR_DTYPE)),
    }

    return xr.Dataset(data_vars=data_vars, coords=coords)


def _build_zarr_encoding(ds: xr.Dataset, chunk_size: int) -> dict:
    """为 Dataset 中的每个变量构建 Zarr 编码配置。"""
    encoding: dict[str, dict] = {}
    for name, da in ds.data_vars.items():
        k = str(name)
        if np.issubdtype(da.dtype, np.floating):
            encoding[k] = {"compressor": _NUM_COMPRESSOR, "chunks": (chunk_size,)}
        elif np.issubdtype(da.dtype, np.integer):
            encoding[k] = {"compressor": _NUM_COMPRESSOR, "chunks": (chunk_size,)}
    for name, da in ds.coords.items():
        k = str(name)
        if da.dtype.kind in ("U", "S", "O"):
            encoding[k] = {"compressor": _STR_COMPRESSOR, "chunks": (chunk_size,)}
        elif np.issubdtype(da.dtype, np.integer):
            encoding[k] = {"compressor": _NUM_COMPRESSOR, "chunks": (chunk_size,)}
    return encoding


def vcf_to_zarr(
    vcf_path: str | Path,
    zarr_path: str | Path,
    *,
    chunk_size: int = 500_000,
) -> StudyMetadata:
    """将单个 VCF.gz 文件转换为 Zarr 存储。

    Parameters
    ----------
    vcf_path : str | Path
        VCF.gz 文件路径（需同目录下有 .tbi 索引）。
    zarr_path : str | Path
        输出 Zarr 目录路径。
    chunk_size : int
        Zarr 分块大小（每个 chunk 包含的变异数量），默认 500,000。

    Returns
    -------
    StudyMetadata
        解析出的研究元信息。

    Examples
    --------
    >>> meta = vcf_to_zarr(
    ...     "/data/mr/ebi-a-GCST90093110/ebi-a-GCST90093110.vcf.gz",
    ...     "/data/mr/ebi-a-GCST90093110.zarr",
    ... )
    """
    vcf_path = Path(vcf_path)
    zarr_path = Path(zarr_path)

    if not vcf_path.exists():
        raise FileNotFoundError(f"VCF 文件不存在: {vcf_path}")
    tbi_path = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
    if not tbi_path.exists():
        raise FileNotFoundError(f"Tabix 索引不存在: {tbi_path}")

    vcf = VCF(str(vcf_path))
    meta = _parse_sample_header(vcf, str(vcf_path))
    vcf.close()

    # 探测实际可用的 FORMAT 字段
    vcf = VCF(str(vcf_path))
    format_fields = _detect_format_fields(vcf)
    vcf.close()

    print(f"[pymr] 转换 {meta.study_id} ({meta.study_type}), "
          f"FORMAT 字段: {format_fields}")

    # 获取所有标准染色体 CONTIG
    vcf = VCF(str(vcf_path))
    chroms: list[str] = []
    for h in vcf.header_iter():
        if h["HeaderType"] == "CONTIG":
            cid = h["ID"]
            if cid in _CHROM_MAP:
                chroms.append(cid)
    vcf.close()
    chroms.sort(key=lambda c: _CHROM_MAP[c])

    # 按染色体分块读取并写入 Zarr
    zarr_path.mkdir(parents=True, exist_ok=True)

    total_written = 0
    for ci, chrom in enumerate(chroms):
        print(f"[pymr] 处理染色体 {chrom} ({ci+1}/{len(chroms)})...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            chunks = _read_chrom_chunk(str(vcf_path), chrom, format_fields, chunk_size)

            if not chunks:
                continue

            ds = xr.concat(chunks, dim="variant")
            n_variants = ds.sizes["variant"]
            chunks.clear()

            encoding = _build_zarr_encoding(ds, chunk_size)

            if total_written == 0:
                ds.to_zarr(str(zarr_path), mode="w", encoding=encoding, compute=True)
            else:
                ds.to_zarr(str(zarr_path), mode="a", append_dim="variant", compute=True)

            total_written += n_variants
            del ds
        print(f"[pymr]   染色体 {chrom}: {n_variants:,} 变异, 累计: {total_written:,}")

    # 写入全局属性
    store = zarr.open(str(zarr_path), mode="a")
    store.attrs.update({
        "study_id": meta.study_id,
        "study_type": meta.study_type,
        "total_variants": meta.total_variants,
        "harmonised_variants": meta.harmonised_variants,
        "total_cases": meta.total_cases,
        "total_controls": meta.total_controls,
        "source_vcf": meta.source_vcf,
        "format_fields": ",".join(format_fields),
    })

    print(f"[pymr] 转换完成: {zarr_path} ({total_written:,} 变异)")
    return meta


def dataset_to_zarr(
    dataset_dir: str | Path,
    zarr_dir: str | Path,
    *,
    chunk_size: int = 500_000,
) -> dict[str, StudyMetadata]:
    """将目录下所有 VCF.gz 批量转换为 Zarr。

    目录结构要求：每个 GWAS 数据集为一个子目录，内含 .vcf.gz 和 .tbi 文件。
    例如:
        dataset_dir/
            ebi-a-GCST90093110/
                ebi-a-GCST90093110.vcf.gz
                ebi-a-GCST90093110.vcf.gz.tbi
            ukb-e-574_CSA/
                ukb-e-574_CSA.vcf.gz
                ukb-e-574_CSA.vcf.gz.tbi

    Parameters
    ----------
    dataset_dir : str | Path
        包含 GWAS 数据集子目录的根目录。
    zarr_dir : str | Path
        输出 Zarr 文件的根目录，每个数据集生成一个 .zarr 子目录。
    chunk_size : int
        Zarr 分块大小。

    Returns
    -------
    dict[str, StudyMetadata]
        各数据集的元信息，键为数据集名称。
    """
    dataset_dir = Path(dataset_dir)
    zarr_dir = Path(zarr_dir)

    vcf_files = sorted(dataset_dir.glob("*/**/*.vcf.gz"))
    if not vcf_files:
        raise FileNotFoundError(f"未找到 VCF.gz 文件: {dataset_dir}")

    results: dict[str, StudyMetadata] = {}
    for vcf_path in vcf_files:
        study_name = vcf_path.stem  # 去掉 .vcf.gz
        zarr_path = zarr_dir / f"{study_name}.zarr"

        if zarr_path.exists():
            print(f"[pymr] 跳过已存在: {zarr_path}")
            continue

        meta = vcf_to_zarr(vcf_path, zarr_path, chunk_size=chunk_size)
        results[study_name] = meta

    return results


# ---------------------------------------------------------------------------
# Load from Zarr
# ---------------------------------------------------------------------------


def _resolve_study_path(study_dir: Path) -> Path:
    """从研究目录解析出 Zarr 路径，不存在则从 VCF.gz 自动转换。"""
    study_name = study_dir.name

    # 优先查找同目录下的 .zarr
    zarr_path = study_dir / f"{study_name}.zarr"
    if zarr_path.exists():
        return zarr_path

    # 回退到 VCF.gz
    vcf_path = study_dir / f"{study_name}.vcf.gz"
    if vcf_path.exists():
        print(f"[pymr] 自动转换: {vcf_path} → {zarr_path}")
        vcf_to_zarr(vcf_path, zarr_path)
        return zarr_path

    raise FileNotFoundError(
        f"在 {study_dir} 下未找到 {study_name}.zarr 或 {study_name}.vcf.gz"
    )


def load_gwas(
    path: str | Path,
    *,
    chrom: str | int | None = None,
    chunks: dict | None = None,
    chunk_size: int = 500_000,
) -> xr.Dataset:
    """加载 GWAS summary statistics。

    传入研究数据目录，自动查找 .zarr 或从 .vcf.gz 转换后加载。

    Parameters
    ----------
    path : str | Path
        研究数据目录，例如 ``/data/mr/ebi-a-GCST90093110``。
        目录下需包含 ``{name}.zarr`` 或 ``{name}.vcf.gz`` + ``.tbi``。
    chrom : str | int | None
        按染色体筛选。支持 '1'-'22', 'X', 'Y', 'MT' 或对应的整数 1-25。
        为 None 时加载全部数据。
    chunks : dict | None
        dask 分块配置，例如 ``{"variant": 100_000}``。
        为 None 时直接加载到内存（非惰性）。
    chunk_size : int
        仅在 VCF→Zarr 自动转换时使用，每个 chunk 包含的变异数量。

    Returns
    -------
    xr.Dataset

    Examples
    --------
    >>> ds = load_gwas("/data/mr/ebi-a-GCST90093110")
    >>> ds = load_gwas("/data/mr/ebi-a-GCST90093110", chrom="1",
    ...                chunks={"variant": 100_000})
    """
    study_dir = Path(path)
    zarr_path = _resolve_study_path(study_dir)

    ds = xr.open_zarr(str(zarr_path), chunks=chunks)  # type: ignore[arg-type]

    if chrom is not None:
        chrom_int = _CHROM_MAP.get(str(chrom), int(chrom)) if isinstance(chrom, str) else int(chrom)
        ds = ds.sel(variant=ds.coords["chrom"] == chrom_int)

    return ds


def load_gwas_dataset(
    zarr_dir: str | Path,
    *,
    name: str | None = None,
    chrom: str | int | None = None,
    chunks: dict | None = None,
) -> xr.Dataset:
    """从 Zarr 目录加载指定 GWAS 数据集。

    Parameters
    ----------
    zarr_dir : str | Path
        Zarr 文件根目录。
    name : str | None
        数据集名称（对应 ``{name}.zarr``）。为 None 时自动选择第一个。
    chrom : str | int | None
        按染色体筛选。
    chunks : dict | None
        dask 分块配置。

    Returns
    -------
    xr.Dataset

    Examples
    --------
    >>> ds = load_gwas_dataset("/data/mr_zarr/", name="ebi-a-GCST90093110")
    """
    zarr_dir = Path(zarr_dir)

    if name is not None:
        zarr_path = zarr_dir / f"{name}.zarr"
    else:
        zarr_files = list(zarr_dir.glob("*.zarr"))
        if not zarr_files:
            raise FileNotFoundError(f"未找到 .zarr 目录: {zarr_dir}")
        zarr_path = zarr_files[0]

    return load_gwas(zarr_path, chrom=chrom, chunks=chunks)
