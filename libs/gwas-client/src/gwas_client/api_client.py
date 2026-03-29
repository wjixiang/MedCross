"""GWAS API 抽象接口模块。

定义了 GWAS 数据获取的通用抽象基类，所有具体 API 实现均需继承此类。
"""

from abc import ABC, abstractmethod
from typing import Any


class IApiClient(ABC):
    """GWAS 数据获取的抽象接口。

    子类需实现所有标注为 ``@abstractmethod`` 的方法。
    通过 ``close()`` 释放底层资源，建议配合上下文管理器使用。
    """

    # ── 基础服务 ─────────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self) -> Any:
        """检查 API 服务是否正常运行。"""

    @abstractmethod
    def get_user(self) -> Any:
        """获取当前认证用户信息，可用于验证 token 有效性。"""

    # ── GWAS 元数据 ──────────────────────────────────────────────────────

    @abstractmethod
    def get_all_gwas_info(self) -> Any:
        """获取当前用户有权限访问的所有 GWAS 数据集的元数据。

        Returns:
            全量 GWAS 数据集元数据列表，每条记录包含 id、trait、sample_size 等字段。
        """

    @abstractmethod
    def get_gwas_info(self, id_list: list[str]) -> Any:
        """按 ID 批量查询特定 GWAS 数据集的元数据。

        Args:
            id_list: GWAS 数据集 ID 列表，如 ``['ieu-a-2', 'ieu-a-7']``。

        Returns:
            匹配的数据集元数据列表。
        """

    @abstractmethod
    def get_gwas_files(self, id_list: list[str]) -> Any:
        """获取指定数据集的文件下载链接（.vcf.gz, .vcf.gz.tbi, _report.html）。

        .. note::
            返回的下载链接有效期仅为 2 小时。

        Args:
            id_list: GWAS 数据集 ID 列表。

        Returns:
            每个数据集对应的文件 URL 字典；若数据集不存在或无权限则不包含在结果中。
        """

    # ── 关联分析 ────────────────────────────────────────────────────────

    @abstractmethod
    def get_associations(self, variant: list[str], id: list[str]) -> Any:
        """查询特定变异在特定 GWAS 数据集中的关联信息。

        Args:
            variant: 变异标识列表，支持 rsID（如 ``'rs1205'``）或
                     chr:pos 格式（如 ``'7:105561135'``，hg19/b37 坐标）。
            id:      GWAS 数据集 ID 列表，如 ``['ieu-a-2', 'ieu-a-7']``。

        Returns:
            变异-表型关联记录列表，包含 beta、se、pval、ea、oa 等字段。
        """

    @abstractmethod
    def get_top_hits(self, id: list[str]) -> Any:
        """从指定 GWAS 数据集中提取满足 p 值阈值的显著位点（Top Hits）。

        Args:
            id: GWAS 数据集 ID 列表。

        Returns:
            经过 LD clumping 后的显著位点列表。
        """

    @abstractmethod
    def get_phewas(self, variant: list[str]) -> Any:
        """对指定变异进行全表型关联扫描（PheWAS）。

        搜索范围涵盖所有可用 GWAS 数据集，仅返回 p <= 0.01 的关联。

        Args:
            variant: 变异标识列表，支持 rsID 或 chr:pos 格式。

        Returns:
            跨数据集的表型关联结果列表。
        """

    # ── 变异信息 ────────────────────────────────────────────────────────

    @abstractmethod
    def get_variants_by_rsid(self, rsid: list[str]) -> Any:
        """通过 rsID 查询变异详细信息（坐标、等位基因等）。

        Args:
            rsid: rs ID 列表，如 ``['rs1205', 'rs234']``。
        """

    @abstractmethod
    def get_variants_by_chrpos(self, chrpos: list[str]) -> Any:
        """通过染色体位置查询变异信息（hg19/b37 坐标）。

        Args:
            chrpos: chr:pos 格式列表，支持范围查询，
                    如 ``['7:105561135', '7:105561135-105563135']``。
        """

    @abstractmethod
    def get_variants_by_gene(self, gene: str) -> Any:
        """查询基因区域内的变异信息。

        Args:
            gene: 基因标识，支持 Ensembl ID（如 ``'ENSG00000123374'``）
                  或 Entrez Gene ID（如 ``'1017'``）。
        """

    # ── 连锁不平衡 (LD) ────────────────────────────────────────────────

    @abstractmethod
    def ld_clump(self) -> Any:
        """对给定的 SNP 列表执行 LD clumping，去除连锁不平衡信号。

        基于 1000 Genomes 参考数据（群体内 MAF > 0.01，仅保留 SNP）。
        """

    @abstractmethod
    def ld_matrix(self, rsid: list[str]) -> Any:
        """计算给定 SNP 列表两两之间的 LD R 值矩阵。

        基于 1000 Genomes 参考数据（群体内 MAF > 0.01，仅保留 SNP）。

        Args:
            rsid: rs ID 列表。
        """

    # ── 资源管理 ────────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭底层 HTTP 连接等资源。"""
