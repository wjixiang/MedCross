from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from .api_client import IApiClient

if TYPE_CHECKING:
    from pathlib import Path

_BASE_URL = "https://api.opengwas.io/api"


class OpenGWAS_API_Client(IApiClient):
    """Client for the IEU OpenGWAS REST API (v4).

    Usage::

        client = OpenGWAS_API_Client(token="your-jwt-token")
        info = client.get_gwas_info(["ieu-a-2", "ieu-a-7"])
        client.close()

    Context manager is also supported::

        with OpenGWAS_API_Client(token="your-jwt-token") as client:
            hits = client.get_top_hits(["ieu-a-2"])
    """

    def __init__(self, token: str | None = None) -> None:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=_BASE_URL, headers=headers, timeout=120.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenGWAS_API_Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── Status ──────────────────────────────────────────────────────────

    def get_status(self) -> Any:
        """GET /status — Check API services are running."""
        return self._get("/status")

    # ── User ────────────────────────────────────────────────────────────

    def get_user(self) -> Any:
        """GET /user — Get current user info (validates token)."""
        return self._get("/user")

    # ── Batches ─────────────────────────────────────────────────────────

    def get_batches(self) -> Any:
        """GET /batches — List existing data batches."""
        return self._get("/batches")

    # ── GWAS Info ───────────────────────────────────────────────────────

    def get_all_gwas_info(self) -> Any:
        """GET /gwasinfo — Get metadata for all accessible GWAS datasets."""
        return self._get("/gwasinfo")

    def get_gwas_info(self, id_list: list[str]) -> Any:
        """POST /gwasinfo — Get metadata for specific GWAS datasets by ID."""
        return self._post("/gwasinfo", params={"id": id_list})

    def get_gwas_files(self, id_list: list[str]) -> Any:
        """POST /gwasinfo/files — Get download URLs for dataset files (.vcf.gz, .tbi, _report.html).

        URLs expire in 2 hours.
        """
        return self._post("/gwasinfo/files", params={"id": id_list})

    # ── Associations ────────────────────────────────────────────────────

    def get_associations(
        self,
        variant: list[str],
        id: list[str],
        *,
        proxies: int = 0,
        population: str = "EUR",
        r2: float = 0.8,
        align_alleles: int = 1,
        palindromes: int = 1,
        maf_threshold: float = 0.3,
    ) -> Any:
        """POST /associations — Get variant associations from GWAS datasets.

        Args:
            variant: rsIDs or chr:pos (hg19/b37), e.g. ['rs1205', '7:105561135'].
            id: GWAS study IDs, e.g. ['ieu-a-2', 'ieu-a-7'].
            proxies: Look for proxy SNPs (1=yes, 0=no).
            population: Reference population for proxies (AFR/AMR/EAS/EUR/SAS).
            r2: Minimum LD r2 for proxies.
            align_alleles: Whether to align alleles (1=yes, 0=no).
            palindromes: Allow palindromic proxies (1=yes, 0=no).
            maf_threshold: Max MAF for palindromic variants.
        """
        return self._post("/associations", params={
            "variant": variant,
            "id": id,
            "proxies": proxies,
            "population": population,
            "r2": r2,
            "align_alleles": align_alleles,
            "palindromes": palindromes,
            "maf_threshold": maf_threshold,
        })

    # ── Top Hits ────────────────────────────────────────────────────────

    def get_top_hits(
        self,
        id: list[str],
        *,
        pval: float = 5e-8,
        preclumped: int = 1,
        clump: int = 1,
        r2: float = 0.001,
        kb: int = 5000,
        pop: str = "EUR",
    ) -> Any:
        """POST /tophits — Extract top hits by p-value threshold.

        Args:
            id: GWAS study IDs.
            pval: P-value threshold (must be <= 0.01).
            preclumped: Use pre-clumped results (1=yes, 0=no).
            clump: Perform clumping (1=yes, 0=no).
            r2: Clumping r2 threshold.
            kb: Clumping window size in kb.
            pop: Population for clumping.
        """
        return self._post("/tophits", params={
            "id": id,
            "pval": pval,
            "preclumped": preclumped,
            "clump": clump,
            "r2": r2,
            "kb": kb,
            "pop": pop,
        })

    # ── PheWAS ──────────────────────────────────────────────────────────

    def get_phewas(
        self,
        variant: list[str],
        *,
        pval: float = 0.01,
        index_list: list[str] | None = None,
    ) -> Any:
        """POST /phewas — PheWAS of variants across all GWAS datasets.

        Only returns associations with p <= 0.01.
        """
        params: dict[str, Any] = {"variant": variant, "pval": pval}
        if index_list:
            params["index_list"] = index_list
        return self._post("/phewas", params=params)

    # ── Variants ────────────────────────────────────────────────────────

    def get_variants_by_rsid(self, rsid: list[str]) -> Any:
        """POST /variants/rsid — Get variant info by rs IDs."""
        return self._post("/variants/rsid", params={"rsid": rsid})

    def get_variants_by_chrpos(
        self,
        chrpos: list[str],
        **kwargs: Any,
    ) -> Any:
        """POST /variants/chrpos — Get variant info by chr:pos (build 37).

        Args:
            chrpos: e.g. ['7:105561135', '7:105561135-105563135'].
            radius: Range to search either side of target locus.
        """
        params: dict[str, Any] = {"chrpos": chrpos, "radius": kwargs.get("radius", 0)}
        return self._post("/variants/chrpos", params=params)

    def get_variants_afl2(
        self,
        *,
        rsid: list[str] | None = None,
        chrpos: list[str] | None = None,
        radius: int = 0,
    ) -> Any:
        """POST /variants/afl2 — Get allele frequency and LD scores."""
        params: dict[str, Any] = {"radius": radius}
        if rsid:
            params["rsid"] = rsid
        if chrpos:
            params["chrpos"] = chrpos
        return self._post("/variants/afl2", params=params)

    def get_afl2_snplist(self) -> Any:
        """GET /variants/afl2/snplist — Get rsids variable across populations."""
        return self._get("/variants/afl2/snplist")

    def get_variants_by_gene(
        self,
        gene: str,
        **kwargs: Any,
    ) -> Any:
        """GET /variants/gene/{gene} — Get variants for a gene (Ensembl or Entrez ID).

        Args:
            gene: e.g. 'ENSG00000123374' or '1017'.
            radius: Range to search either side of target locus.
        """
        return self._get(f"/variants/gene/{gene}", params={"radius": kwargs.get("radius", 0)})

    # ── LD ──────────────────────────────────────────────────────────────

    def ld_clump(self, **kwargs: Any) -> Any:
        """POST /ld/clump — Perform LD clumping on rs IDs.

        Uses 1000 Genomes reference (MAF > 0.01, SNPs only).

        Args:
            rsid: List of rs IDs.
            pval: Corresponding p-values for each rsid.
            pthresh: P-value threshold (default 5e-8).
            r2: LD r2 threshold (default 0.001).
            kb: Clumping window in kb (default 5000).
            pop: Population (EUR/SAS/EAS/AFR/AMR/legacy).
        """
        params: dict[str, Any] = {
            "pthresh": kwargs.get("pthresh", 5e-8),
            "r2": kwargs.get("r2", 0.001),
            "kb": kwargs.get("kb", 5000),
            "pop": kwargs.get("pop", "EUR"),
        }
        if "rsid" in kwargs and kwargs["rsid"]:
            params["rsid"] = kwargs["rsid"]
        if "pval" in kwargs and kwargs["pval"]:
            params["pval"] = kwargs["pval"]
        return self._post("/ld/clump", params=params)

    def ld_matrix(self, rsid: list[str], **kwargs: Any) -> Any:
        """POST /ld/matrix — Get LD R values for SNPs.

        Uses 1000 Genomes reference (MAF > 0.01, SNPs only).
        """
        return self._post("/ld/matrix", params={
            "rsid": rsid,
            "pop": kwargs.get("pop", "EUR"),
        })

    def ld_ref_lookup(self, rsid: list[str], **kwargs: Any) -> Any:
        """POST /ld/reflookup — Check if rsids exist in the LD reference panel."""
        return self._post("/ld/reflookup", params={
            "rsid": rsid,
            "pop": kwargs.get("pop", "EUR"),
        })

    # ── Edit (Upload / Metadata management) ─────────────────────────────

    def add_gwas_metadata(self, **kwargs: Any) -> Any:
        """POST /edit/add — Add new GWAS metadata.

        Required fields: trait, build, group_name, category, subcategory,
        population, sex, author.
        """
        return self._post("/edit/add", params=kwargs)

    def edit_gwas_metadata(self, **kwargs: Any) -> Any:
        """POST /edit/edit — Edit existing GWAS metadata (requires 'id' field)."""
        return self._post("/edit/edit", params=kwargs)

    def list_user_gwas(
        self,
        *,
        state: str = "draft",
        offset: int = 0,
        limit: int = 100,
    ) -> Any:
        """GET /edit/list — List datasets added by the current user."""
        return self._get("/edit/list", params={
            "state": state,
            "offset": offset,
            "limit": limit,
        })

    def get_gwas_metadata(self, gwas_id: str) -> Any:
        """GET /edit/check/{gwas_id} — Get metadata for a specific dataset."""
        return self._get(f"/edit/check/{gwas_id}")

    def get_gwas_state(self, gwas_id: str) -> Any:
        """GET /edit/state/{gwas_id} — Check DAG runs for a dataset."""
        return self._get(f"/edit/state/{gwas_id}")

    def delete_draft_gwas(self, gwas_id: str) -> Any:
        """DELETE /edit/delete/draft/{gwas_id} — Delete a draft dataset."""
        return self._delete(f"/edit/delete/draft/{gwas_id}")

    def upload_gwas(
        self,
        gwas_id: str,
        file_path: str | Path,
        *,
        chr_col: int,
        pos_col: int,
        ea_col: int,
        oa_col: int,
        beta_col: int,
        se_col: int,
        pval_col: int,
        delimiter: str = "tab",
        header: str = "True",
        gzipped: str = "True",
        ncase_col: int | None = None,
        snp_col: int | None = None,
        eaf_col: int | None = None,
        oaf_col: int | None = None,
        imp_z_col: int | None = None,
        imp_info_col: int | None = None,
        ncontrol_col: int | None = None,
        md5: str | None = None,
        nsnp: int | None = None,
    ) -> Any:
        """POST /edit/upload — Upload GWAS summary stats file."""
        params: dict[str, Any] = {
            "id": gwas_id,
            "chr_col": chr_col,
            "pos_col": pos_col,
            "ea_col": ea_col,
            "oa_col": oa_col,
            "beta_col": beta_col,
            "se_col": se_col,
            "pval_col": pval_col,
            "delimiter": delimiter,
            "header": header,
            "gzipped": gzipped,
        }
        for key, val in {
            "ncase_col": ncase_col,
            "snp_col": snp_col,
            "eaf_col": eaf_col,
            "oaf_col": oaf_col,
            "imp_z_col": imp_z_col,
            "imp_info_col": imp_info_col,
            "ncontrol_col": ncontrol_col,
            "md5": md5,
            "nsnp": nsnp,
        }.items():
            if val is not None:
                params[key] = val

        with open(file_path, "rb") as f:
            return self._post("/edit/upload", params=params, files={"gwas_file": f})

    # ── Quality Control ─────────────────────────────────────────────────

    def get_qc_todo(self) -> Any:
        """GET /quality_control/list — Get all datasets requiring QC."""
        return self._get("/quality_control/list")

    def get_qc_files(self, dataset_id: str) -> Any:
        """GET /quality_control/check/{id} — View QC files for a dataset."""
        return self._get(f"/quality_control/check/{dataset_id}")

    def get_qc_report(self, gwas_id: str) -> str:
        """GET /quality_control/report/{gwas_id} — Get HTML QC report."""
        resp = self._client.get(f"/quality_control/report/{gwas_id}")
        resp.raise_for_status()
        return resp.text

    def submit_for_approval(self, gwas_id: str) -> Any:
        """GET /quality_control/submit/{gwas_id} — Submit dataset for approval."""
        return self._get(f"/quality_control/submit/{gwas_id}")

    def delete_qc(self, dataset_id: str) -> Any:
        """DELETE /quality_control/delete/{id} — Delete QC relationship."""
        return self._delete(f"/quality_control/delete/{dataset_id}", params={"id": dataset_id})

    def release_qc(
        self,
        dataset_id: str,
        passed_qc: str,
        *,
        comments: str | None = None,
    ) -> Any:
        """POST /quality_control/release — Release data from QC process.

        Args:
            dataset_id: GWAS dataset identifier.
            passed_qc: 'True' or 'False'.
            comments: Optional reviewer comments.
        """
        params: dict[str, Any] = {"id": dataset_id, "passed_qc": passed_qc}
        if comments:
            params["comments"] = comments
        return self._post("/quality_control/release", params=params)

    # ── Internal HTTP helpers ───────────────────────────────────────────

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        resp = self._client.post(path, params=params, files=files)
        resp.raise_for_status()
        return resp.json()

    def _delete(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        resp = self._client.delete(path, params=params)
        resp.raise_for_status()
        return resp.json()
