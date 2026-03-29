from abc import ABC, abstractmethod
from typing import Any


class IApiClient(ABC):
    """Abstract interface for GWAS data fetching."""

    @abstractmethod
    def get_status(self) -> Any:
        """Check API services are running."""

    @abstractmethod
    def get_user(self) -> Any:
        """Get current user info."""

    @abstractmethod
    def get_all_gwas_info(self) -> Any:
        """Get metadata for all accessible GWAS datasets."""

    @abstractmethod
    def get_gwas_info(self, id_list: list[str]) -> Any:
        """Get metadata for specific GWAS datasets by ID."""

    @abstractmethod
    def get_gwas_files(self, id_list: list[str]) -> Any:
        """Get download URLs for dataset files."""

    @abstractmethod
    def get_associations(self, variant: list[str], id: list[str]) -> Any:
        """Get variant associations from GWAS datasets."""

    @abstractmethod
    def get_top_hits(self, id: list[str]) -> Any:
        """Extract top hits by p-value threshold."""

    @abstractmethod
    def get_phewas(self, variant: list[str]) -> Any:
        """PheWAS of variants across GWAS datasets."""

    @abstractmethod
    def get_variants_by_rsid(self, rsid: list[str]) -> Any:
        """Get variant info by rs IDs."""

    @abstractmethod
    def get_variants_by_chrpos(self, chrpos: list[str]) -> Any:
        """Get variant info by chr:pos (build 37)."""

    @abstractmethod
    def get_variants_by_gene(self, gene: str) -> Any:
        """Get variant info for a gene."""

    @abstractmethod
    def ld_clump(self) -> Any:
        """Perform LD clumping."""

    @abstractmethod
    def ld_matrix(self, rsid: list[str]) -> Any:
        """Get LD R values for SNPs."""

    def close(self) -> None:
        """Close any open resources."""
