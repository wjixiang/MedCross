from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from pride_client.api_client import API_Client, PRIDE_API_Client_Config
from pride_client.models import (
    PRIDEAPProject,
    PRIDEAPProteinSearchQuery,
    PRIDEAPSearchQuery,
    PRIDEFacetQuery,
    PRIDEFile,
    PRIDEProjectDownloadLinks,
    PRIDEProjectMetadata,
    PRIDE_Project,
    PRIDE_Project_Summary,
    PRIDEProjectsByProtein,
    PRIDEProjectsByProteinWrapper,
    PRIDESearchQuery,
    Protein,
    ProteinAccessionsPageResponse,
)

_default_config = PRIDE_API_Client_Config(
    baseUrl="https://www.ebi.ac.uk/pride/ws/archive/v3"
)


def get_client(config: PRIDE_API_Client_Config | None = None) -> API_Client:
    return API_Client(config or _default_config)


def _run(coro):
    return asyncio.run(coro)


def search_projects(query: PRIDESearchQuery) -> tuple[list[PRIDE_Project_Summary], int]:
    return _run(get_client().searchProjects(query))


def get_project(accession: str) -> PRIDE_Project:
    return _run(get_client().retrieveProjectById(accession))


def get_project_download_links(accession: str) -> PRIDEProjectDownloadLinks:
    return _run(get_client().downloadProject(accession=accession))


def get_projects(page: int = 0, page_size: int = 100) -> list[PRIDE_Project]:
    return _run(get_client().getProjects(page=page, pageSize=page_size))


def get_projects_metadata(
    page: int = 0, page_size: int = 100
) -> list[PRIDEProjectMetadata]:
    return _run(get_client().getProjectsMetadata(page=page, pageSize=page_size))


def get_project_count() -> int:
    return _run(get_client().getCountOfAllProjects())


def get_project_status(accession: str) -> str:
    return _run(get_client().getProjectStatus(accession=accession))


def get_similar_projects(
    accession: str, page: int = 0, page_size: int = 100
) -> list[PRIDE_Project_Summary]:
    return _run(
        get_client().getSimilarProjects(
            accession=accession, page=page, pageSize=page_size
        )
    )


def get_reanalysis_project(accession: str) -> PRIDE_Project:
    return _run(get_client().getReanalysisProject(projectAccession=accession))


def autocomplete(keyword: str) -> list[str]:
    return _run(get_client().autocomplete(keyword=keyword))


def get_facets(query: PRIDEFacetQuery) -> Dict[str, Dict[str, int]]:
    return _run(get_client().getFacets(query=query))


def get_file(file_accession: str) -> PRIDEFile:
    return _run(get_client().getFile(fileAccession=file_accession))


def get_project_files(
    project_accession: str,
    page: int = 0,
    page_size: int = 100,
    filename_filter: str = "",
) -> list[PRIDEFile]:
    return _run(
        get_client().getFilesByProject(
            projectAccession=project_accession,
            page=page,
            pageSize=page_size,
            filenameFilter=filename_filter,
        )
    )


def get_all_project_files(
    project_accession: str,
    filename_filter: str = "",
) -> list[PRIDEFile]:
    return _run(
        get_client().getAllFilesByProject(
            projectAccession=project_accession,
            filenameFilter=filename_filter,
        )
    )


def get_project_file_count(project_accession: str) -> int:
    return _run(get_client().getCountOfProjectFiles(projectAccession=project_accession))


def get_sdrf_files(project_accession: str) -> list[str]:
    return _run(get_client().getSDRFFiles(projectAccession=project_accession))


def get_file_counts_by_type(project_accession: str) -> Dict[str, Any]:
    return _run(get_client().getCountOfFilesByType(projectAccession=project_accession))


def get_total_file_count() -> int:
    return _run(get_client().getCountOfAllFiles())


def get_file_checksums(project_accession: str) -> str:
    return _run(get_client().getFileChecksums(projectAccession=project_accession))


def get_protein_by_accession(accession: str) -> PRIDEProjectsByProtein:
    return _run(get_client().getProteinByAccession(accession=accession))


def search_proteins(accession: str) -> list[PRIDEProjectsByProteinWrapper]:
    return _run(get_client().searchProteins(accession=accession))


def get_all_protein_accessions(
    page_size: int = 100, page_number: int = 0
) -> ProteinAccessionsPageResponse:
    return _run(
        get_client().getAllProteinAccessions(pageSize=page_size, pageNumber=page_number)
    )


def get_stats(name: str) -> Any:
    return _run(get_client().getStats(name=name))


def get_submitted_data_stats() -> Any:
    return _run(get_client().getSubmittedDataStats())


def get_submissions_monthly_tsv() -> str:
    return _run(get_client().getSubmissionsMonthlyTSV())


def get_submissions_monthly() -> Any:
    return _run(get_client().getSubmissionsMonthly())


def get_ap_project(accession: str) -> PRIDEAPProject:
    return _run(get_client().getAPProject(accession=accession))


def search_ap_projects(query: PRIDEAPSearchQuery) -> list[PRIDEAPProject]:
    return _run(get_client().searchAPProjects(query=query))


def search_ap_proteins(query: PRIDEAPProteinSearchQuery) -> list[Protein]:
    return _run(get_client().searchAPProteins(query=query))
