"""IEU OpenGWAS API 客户端实现。

封装了 IEU OpenGWAS 数据库（https://api.opengwas.io）的全部 REST API 端点，
提供类型安全的 Python SDK 接口。

认证方式
--------
所有需要认证的端点使用 JWT Bearer Token。可在 https://api.opengwas.io 注册获取。

Usage::

    from gwas_client import OpenGWAS_API_Client

    # 直接创建并手动关闭
    client = OpenGWAS_API_Client(token="your-jwt-token")
    info = client.get_gwas_info(["ieu-a-2", "ieu-a-7"])
    client.close()

    # 推荐使用上下文管理器
    with OpenGWAS_API_Client(token="your-jwt-token") as client:
        hits = client.get_top_hits(["ieu-a-2"])
        matrix = client.ld_matrix(["rs1205", "rs234"])

注意事项
--------
- OpenGWAS API 有请求速率限制，短时间内大量请求可能返回 401 错误。
- 大部分查询端点坐标基于 hg19/GRCh37 构建。
- LD 相关操作基于 1000 Genomes 参考数据（群体内 MAF > 0.01，仅保留 SNP）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from .api_client import IApiClient

if TYPE_CHECKING:
    from pathlib import Path

_BASE_URL = "https://api.opengwas.io/api"


class OpenGWAS_API_Client(IApiClient):
    """IEU OpenGWAS REST API (v4) 的 Python 客户端。

    覆盖 OpenGWAS 全部 30 个 API 端点，包括：
    状态检查、用户认证、GWAS 元数据查询、变异关联、Top Hits、
    PheWAS、变异信息检索、LD 操作、数据上传编辑和质量控制。

    Args:
        token: JWT Bearer Token，用于认证。
               可在 https://api.opengwas.io 注册获取。
               为 None 时不设置认证头（仅可访问无需认证的端点）。
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

    # ═══════════════════════════════════════════════════════════════════
    #  基础服务
    # ═══════════════════════════════════════════════════════════════════

    def get_status(self) -> Any:
        """GET /status — 检查 API 及关联服务是否正常运行（无需认证）。"""
        return self._get("/status")

    def get_user(self) -> Any:
        """GET /user — 获取当前用户信息。

        可用于验证 token 是否有效（200 OK 表示有效）。
        返回字段包括 uid、account_id、jwt_valid_until、roles 等。
        """
        return self._get("/user")

    # ═══════════════════════════════════════════════════════════════════
    #  数据批次
    # ═══════════════════════════════════════════════════════════════════

    def get_batches(self) -> Any:
        """GET /batches — 列出所有已存在的数据批次（无需认证）。"""
        return self._get("/batches")

    # ═══════════════════════════════════════════════════════════════════
    #  GWAS 元数据
    # ═══════════════════════════════════════════════════════════════════

    def get_all_gwas_info(self) -> Any:
        """GET /gwasinfo — 获取当前用户有权限访问的所有 GWAS 数据集元数据。

        每条记录包含 id、trait、sample_size、nsnp、category、population 等字段。
        数据量较大，首次请求可能需要较长时间。
        """
        return self._get("/gwasinfo")

    def get_gwas_info(self, id_list: list[str]) -> Any:
        """POST /gwasinfo — 按 ID 批量查询 GWAS 数据集元数据。

        Args:
            id_list: GWAS 数据集 ID 列表，如 ``['ieu-a-2', 'ieu-a-7', 'ukb-b-19953']``。
        """
        return self._post("/gwasinfo", params={"id": id_list})

    def get_gwas_files(self, id_list: list[str]) -> Any:
        """POST /gwasinfo/files — 获取数据集关联文件的下载链接。

        返回的文件类型包括：
        - ``.vcf.gz`` — VCF 格式的 summary statistics
        - ``.vcf.gz.tbi`` — VCF 索引文件
        - ``_report.html`` — QC 报告

        .. warning::
            下载链接有效期仅为 **2 小时**，过期后需重新获取。

        Args:
            id_list: GWAS 数据集 ID 列表。
        """
        return self._post("/gwasinfo/files", params={"id": id_list})

    # ═══════════════════════════════════════════════════════════════════
    #  变异关联查询
    # ═══════════════════════════════════════════════════════════════════

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
        """POST /associations — 查询特定变异在特定 GWAS 数据集中的关联信息。

        Args:
            variant:       变异标识列表，支持三种格式：
                           - rsID：``'rs1205'``
                           - chr:pos：``'7:105561135'``
                           - chr:pos 范围：``'7:105561135-105563135'``
                           坐标基于 hg19/b37。
            id:            GWAS 数据集 ID 列表，如 ``['ieu-a-2', 'ieu-a-7']``。
            proxies:       是否查找 LD 代理 SNP（1=是, 0=否），默认 0。
                           注意：范围查询（chr:pos-pos）不支持代理查找。
            population:    代理查找的参考群体，默认 ``'EUR'``。
                           可选：``AFR``, ``AMR``, ``EAS``, ``EUR``, ``SAS``。
            r2:            代理 SNP 的最小 LD r2 阈值（>= 该值），默认 0.8。
            align_alleles: 是否进行等位基因比对（1=是, 0=否），默认 1。
            palindromes:   是否允许回文序列的代理 SNP（1=是, 0=否），默认 1。
            maf_threshold: 回文变异的最大允许 MAF（< 该值），默认 0.3。

        Returns:
            关联记录列表，每条包含 pval、beta、se、ea、oa、eaf 等字段。
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

    # ═══════════════════════════════════════════════════════════════════
    #  Top Hits
    # ═══════════════════════════════════════════════════════════════════

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
        """POST /tophits — 从 GWAS 数据集中提取满足 p 值阈值的显著位点。

        支持自动 LD clumping 去冗余，或使用预计算结果。

        Args:
            id:          GWAS 数据集 ID 列表。
            pval:        p 值阈值，必须 <= 0.01，默认 5e-8（全基因组显著性水平）。
            preclumped:  是否使用预计算的 clumped 结果（1=是, 0=否），默认 1。
            clump:       是否执行 clumping（1=是, 0=否），默认 1。
            r2:          clumping 的 r2 阈值，默认 0.001。
            kb:          clumping 的窗口大小（kb），默认 5000。
            pop:         clumping 使用的参考群体，默认 ``'EUR'``。
                         可选：``EUR``, ``SAS``, ``EAS``, ``AFR``, ``AMR``, ``legacy``。
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

    # ═══════════════════════════════════════════════════════════════════
    #  PheWAS（全表型关联扫描）
    # ═══════════════════════════════════════════════════════════════════

    def get_phewas(
        self,
        variant: list[str],
        *,
        pval: float = 0.01,
        index_list: list[str] | None = None,
    ) -> Any:
        """POST /phewas — 对指定变异进行全表型关联扫描。

        搜索范围涵盖所有可用 GWAS 数据集，仅返回 p <= 指定阈值的关联结果。

        Args:
            variant:    变异标识列表，支持 rsID 或 chr:pos 格式（hg19/b37）。
            pval:       p 值阈值，必须 <= 0.01，默认 0.01。
            index_list: 限定搜索的数据集索引列表；为 None 时搜索全部数据集。
        """
        params: dict[str, Any] = {"variant": variant, "pval": pval}
        if index_list:
            params["index_list"] = index_list
        return self._post("/phewas", params=params)

    # ═══════════════════════════════════════════════════════════════════
    #  变异信息
    # ═══════════════════════════════════════════════════════════════════

    def get_variants_by_rsid(self, rsid: list[str]) -> Any:
        """POST /variants/rsid — 通过 rsID 查询变异详细信息。

        Args:
            rsid: rs ID 列表，如 ``['rs1205', 'rs234']``。

        Returns:
            变异信息列表，包含 chr、pos、rsid、ea、oa、eaf 等字段。
        """
        return self._post("/variants/rsid", params={"rsid": rsid})

    def get_variants_by_chrpos(
        self,
        chrpos: list[str],
        **kwargs: Any,
    ) -> Any:
        """POST /variants/chrpos — 通过染色体位置查询变异信息（hg19/b37）。

        Args:
            chrpos: chr:pos 格式列表，支持范围查询，
                    如 ``['7:105561135', '7:105561135-105563135']``。
            radius: （关键字参数）搜索目标位点两侧的范围（bp），默认 0。
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
        """POST /variants/afl2 — 获取变异的等位基因频率和 LD score。

        至少提供 ``rsid`` 或 ``chrpos`` 其中之一。

        Args:
            rsid:   rs ID 列表。
            chrpos: chr:pos 格式列表（hg19/b37）。
            radius: 搜索范围（仅对 chrpos 查询生效），默认 0。
        """
        params: dict[str, Any] = {"radius": radius}
        if rsid:
            params["rsid"] = rsid
        if chrpos:
            params["chrpos"] = chrpos
        return self._post("/variants/afl2", params=params)

    def get_afl2_snplist(self) -> Any:
        """GET /variants/afl2/snplist — 获取跨群体变异频率差异显著的 SNP 列表。

        常用于群体遗传学和祖先推断分析。
        """
        return self._get("/variants/afl2/snplist")

    def get_variants_by_gene(
        self,
        gene: str,
        **kwargs: Any,
    ) -> Any:
        """GET /variants/gene/{gene} — 查询基因区域内的变异信息。

        Args:
            gene:   基因标识，支持 Ensembl ID（如 ``'ENSG00000123374'``）
                    或 Entrez Gene ID（如 ``'1017'``，即 CDK2）。
            radius: （关键字参数）搜索基因两侧的范围（bp），默认 0。
        """
        return self._get(f"/variants/gene/{gene}", params={"radius": kwargs.get("radius", 0)})

    # ═══════════════════════════════════════════════════════════════════
    #  连锁不平衡 (LD) 操作
    #  基于 1000 Genomes 参考数据（群体内 MAF > 0.01，仅保留 SNP）
    # ═══════════════════════════════════════════════════════════════════

    def ld_clump(self, **kwargs: Any) -> Any:
        """POST /ld/clump — 对 SNP 列表执行 LD clumping。

        在每个 LD block 中仅保留 p 值最小的 SNP（index SNP），
        去除与其高度连锁的冗余信号。

        Args:
            rsid:    SNP 的 rs ID 列表。
            pval:    每个 rsid 对应的 p 值列表（与 rsid 一一对应）。
            pthresh: index SNP 的 p 值阈值，默认 5e-8。
            r2:      LD r2 阈值（>= 该值视为连锁），默认 0.001。
            kb:      clumping 窗口大小（kb），默认 5000。
            pop:     参考群体，默认 ``'EUR'``。
                     可选：``EUR``, ``SAS``, ``EAS``, ``AFR``, ``AMR``, ``legacy``。
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
        """POST /ld/matrix — 计算 SNP 列表两两之间的 LD R 值矩阵。

        结果以第一个 SNP 为参考等位基因方向。

        Args:
            rsid: rs ID 列表（建议不超过 500 个，否则计算耗时较长）。
            pop:  参考群体，默认 ``'EUR'``。
        """
        return self._post("/ld/matrix", params={
            "rsid": rsid,
            "pop": kwargs.get("pop", "EUR"),
        })

    def ld_ref_lookup(self, rsid: list[str], **kwargs: Any) -> Any:
        """POST /ld/reflookup — 检查 rsid 是否存在于 LD 参考面板中。

        常用于在进行 LD 操作前验证 SNP 是否可用。

        Args:
            rsid: rs ID 列表。
            pop:  参考群体，默认 ``'EUR'``。
        """
        return self._post("/ld/reflookup", params={
            "rsid": rsid,
            "pop": kwargs.get("pop", "EUR"),
        })

    # ═══════════════════════════════════════════════════════════════════
    #  数据编辑与管理（需要相应权限）
    # ═══════════════════════════════════════════════════════════════════

    def add_gwas_metadata(self, **kwargs: Any) -> Any:
        """POST /edit/add — 添加新的 GWAS 数据集元数据。

        必填字段：``trait``, ``build``, ``group_name``, ``category``,
        ``subcategory``, ``population``, ``sex``, ``author``。

        可选字段包括：``id``, ``nsnp``, ``sample_size``, ``year``, ``ontology``,
        ``unit``, ``ncase``, ``ncontrol``, ``study_design``, ``covariates``,
        ``coverage``, ``qc_prior_to_upload``, ``imputation_panel``,
        ``beta_transformation``, ``doi``, ``consortium``, ``pmid``, ``sd``,
        ``mr``, ``priority``, ``note``。

        详细的枚举值请参考 https://api.opengwas.io/api/docs#/default/edit_add_metadata。
        """
        return self._post("/edit/add", params=kwargs)

    def edit_gwas_metadata(self, **kwargs: Any) -> Any:
        """POST /edit/edit — 编辑已有 GWAS 数据集的元数据。

        必须提供 ``id`` 字段指定要编辑的数据集。
        其他字段与 ``add_gwas_metadata`` 相同。
        """
        return self._post("/edit/edit", params=kwargs)

    def list_user_gwas(
        self,
        *,
        state: str = "draft",
        offset: int = 0,
        limit: int = 100,
    ) -> Any:
        """GET /edit/list — 列出当前用户添加的数据集。

        Args:
            state:  筛选状态：``'draft'``（未发布）或 ``'released'``（已发布），默认 ``'draft'``。
            offset: 分页偏移量（仅 ``state='released'`` 时生效），默认 0。
            limit:  分页大小（仅 ``state='released'`` 时生效），默认 100。
        """
        return self._get("/edit/list", params={
            "state": state,
            "offset": offset,
            "limit": limit,
        })

    def get_gwas_metadata(self, gwas_id: str) -> Any:
        """GET /edit/check/{gwas_id} — 获取指定数据集的完整元数据。

        Args:
            gwas_id: GWAS 数据集 ID。
        """
        return self._get(f"/edit/check/{gwas_id}")

    def get_gwas_state(self, gwas_id: str) -> Any:
        """GET /edit/state/{gwas_id} — 查看数据集的处理流水线（DAG）运行状态。

        用于跟踪上传数据集的 QC 处理进度。

        Args:
            gwas_id: GWAS 数据集 ID。
        """
        return self._get(f"/edit/state/{gwas_id}")

    def delete_draft_gwas(self, gwas_id: str) -> Any:
        """DELETE /edit/delete/draft/{gwas_id} — 删除草稿数据集。

        将强制 QC 流水线失败，删除已上传的文件和 QC 产物。
        仅在数据集提交审批之前可用。

        Args:
            gwas_id: 要删除的 GWAS 数据集 ID。
        """
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
        """POST /edit/upload — 上传 GWAS summary statistics 文件。

        上传前需先通过 ``add_gwas_metadata()`` 创建数据集元数据。

        Args:
            gwas_id:    数据集 ID（需与已创建的元数据 ID 一致）。
            file_path:  本地文件路径，支持 gzip 压缩文件。
            chr_col:    染色体列的列索引（从 1 开始）。
            pos_col:    位置列的列索引。
            ea_col:     效应等位基因列的列索引。
            oa_col:     非效应等位基因列的列索引。
            beta_col:   效应值（beta）列的列索引。
            se_col:     标准误列的列索引。
            pval_col:   p 值列的列索引。
            delimiter:  列分隔符：``'tab'``, ``'comma'``, ``'space'``，默认 ``'tab'``。
            header:     文件是否包含表头行：``'True'`` 或 ``'False'``，默认 ``'True'``。
            gzipped:    文件是否为 gzip 压缩：``'True'`` 或 ``'False'``，默认 ``'True'``。
            ncase_col:  病例数列索引（可选）。
            snp_col:    dbsnp rs ID 列索引（可选）。
            eaf_col:    效应等位基因频率列索引（可选）。
            oaf_col:    非效应等位基因频率列索引（可选）。
            imp_z_col:  imputation Z score 列索引（可选）。
            imp_info_col: imputation INFO score 列索引（可选）。
            ncontrol_col: 对照数列索引；连续性状时为总样本量（可选）。
            md5:        上传文件的 MD5 校验值（可选，用于完整性验证）。
            nsnp:       文件中的 SNP 数量（可选）。
        """
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

    # ═══════════════════════════════════════════════════════════════════
    #  质量控制（需要 QC reviewer 权限）
    # ═══════════════════════════════════════════════════════════════════

    def get_qc_todo(self) -> Any:
        """GET /quality_control/list — 获取所有待 QC 审核的数据集列表。

        需要 QC reviewer 权限。
        """
        return self._get("/quality_control/list")

    def get_qc_files(self, dataset_id: str) -> Any:
        """GET /quality_control/check/{id} — 查看数据集 QC 过程中生成的文件。

        Args:
            dataset_id: GWAS 数据集 ID。
        """
        return self._get(f"/quality_control/check/{dataset_id}")

    def get_qc_report(self, gwas_id: str) -> str:
        """GET /quality_control/report/{gwas_id} — 获取数据集的 HTML 格式 QC 报告。

        Args:
            gwas_id: GWAS 数据集 ID。

        Returns:
            HTML 格式的 QC 报告内容。
        """
        resp = self._client.get(f"/quality_control/report/{gwas_id}")
        resp.raise_for_status()
        return resp.text

    def submit_for_approval(self, gwas_id: str) -> Any:
        """GET /quality_control/submit/{gwas_id} — 提交数据集供审批发布。

        Args:
            gwas_id: GWAS 数据集 ID。
        """
        return self._get(f"/quality_control/submit/{gwas_id}")

    def delete_qc(self, dataset_id: str) -> Any:
        """DELETE /quality_control/delete/{id} — 删除 QC 关联记录。

        仅删除 QC 关联关系，不删除元数据或数据文件。

        Args:
            dataset_id: GWAS 数据集 ID。
        """
        return self._delete(f"/quality_control/delete/{dataset_id}", params={"id": dataset_id})

    def release_qc(
        self,
        dataset_id: str,
        passed_qc: str,
        *,
        comments: str | None = None,
    ) -> Any:
        """POST /quality_control/release — 完成 QC 审核并发布或拒绝数据集。

        Args:
            dataset_id: GWAS 数据集 ID。
            passed_qc:  是否通过 QC：``'True'`` 或 ``'False'``。
            comments:   审核意见备注（可选）。
        """
        params: dict[str, Any] = {"id": dataset_id, "passed_qc": passed_qc}
        if comments:
            params["comments"] = comments
        return self._post("/quality_control/release", params=params)

    # ═══════════════════════════════════════════════════════════════════
    #  内部 HTTP 工具方法
    # ═══════════════════════════════════════════════════════════════════

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
