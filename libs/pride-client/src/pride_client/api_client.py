from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

from .models import (
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


class PRIDE_API_Client_Config(BaseModel):
    baseUrl: str
    timeout: int = Field(default=30, description="Request timeout in seconds")


defaultPRIDEApiClientConfig = PRIDE_API_Client_Config(
    baseUrl="https://www.ebi.ac.uk/pride/ws/archive/v3"
)


class API_Client:
    config: PRIDE_API_Client_Config

    def __init__(self, config: Optional[PRIDE_API_Client_Config] = None) -> None:
        self.config = config or defaultPRIDEApiClientConfig

    async def _get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(f"{self.config.baseUrl}{path}", params=params)
            response.raise_for_status()
            return response

    # ── Projects ─────────────────────────────────────────────────────────

    async def retrieveProjectById(self, projectId: str) -> PRIDE_Project:
        response = await self._get(f"/projects/{projectId}")
        data = response.json()
        try:
            return PRIDE_Project.model_validate(data)
        except ValidationError as e:
            raise ValidationError(
                f"Failed to validate PRIDE project data for '{projectId}'. "
                f"Validation errors: {e.errors()}",
                PRIDE_Project,
                data,
            ) from e

    async def getProjects(
        self, page: int = 0, pageSize: int = 100
    ) -> List[PRIDE_Project]:
        response = await self._get(
            "/projects", params={"page": page, "pageSize": pageSize}
        )
        return [PRIDE_Project.model_validate(item) for item in response.json()]

    async def getProjectsMetadata(
        self, page: int = 0, pageSize: int = 100
    ) -> List[PRIDEProjectMetadata]:
        response = await self._get(
            "/projects/metadata", params={"page": page, "pageSize": pageSize}
        )
        return [PRIDEProjectMetadata.model_validate(item) for item in response.json()]

    async def getCountOfAllProjects(self) -> int:
        response = await self._get("/projects/count")
        return int(response.text)

    async def getProjectStatus(self, accession: str) -> str:
        response = await self._get(f"/status/{accession}")
        return response.text

    async def getSimilarProjects(
        self, accession: str, page: int = 0, pageSize: int = 100
    ) -> List[PRIDE_Project_Summary]:
        response = await self._get(
            f"/projects/{accession}/similarProjects",
            params={"page": page, "pageSize": pageSize},
        )
        return [PRIDE_Project_Summary.model_validate(item) for item in response.json()]

    async def getReanalysisProject(self, projectAccession: str) -> PRIDE_Project:
        response = await self._get(f"/projects/reanalysis/{projectAccession}")
        return PRIDE_Project.model_validate(response.json())

    async def downloadProject(self, accession: str) -> PRIDEProjectDownloadLinks:
        response = await self._get(f"/projects/files-path/{accession}")
        return PRIDEProjectDownloadLinks.model_validate(response.json())

    # ── Search ───────────────────────────────────────────────────────────

    async def searchProjects(
        self, query: PRIDESearchQuery
    ) -> tuple[List[PRIDE_Project_Summary], int]:
        response = await self._get("/search/projects", params=query.model_dump())
        total = int(response.headers.get("total_records", 0))
        data = response.json()
        return [PRIDE_Project_Summary.model_validate(item) for item in data], total

    async def autocomplete(self, keyword: str) -> List[str]:
        response = await self._get("/search/autocomplete", params={"keyword": keyword})
        return response.json()

    async def getFacets(self, query: PRIDEFacetQuery) -> Dict[str, Dict[str, int]]:
        response = await self._get("/facet/projects", params=query.model_dump())
        return response.json()

    # ── Files ────────────────────────────────────────────────────────────

    async def getFile(self, fileAccession: str) -> PRIDEFile:
        response = await self._get(f"/files/{fileAccession}")
        return PRIDEFile.model_validate(response.json())

    async def getFilesByProject(
        self,
        projectAccession: str,
        page: int = 0,
        pageSize: int = 100,
        filenameFilter: str = "",
    ) -> List[PRIDEFile]:
        response = await self._get(
            f"/projects/{projectAccession}/files",
            params={
                "page": page,
                "pageSize": pageSize,
                "filenameFilter": filenameFilter,
            },
        )
        return [PRIDEFile.model_validate(item) for item in response.json()]

    async def getAllFilesByProject(
        self,
        projectAccession: str,
        filenameFilter: str = "",
    ) -> List[PRIDEFile]:
        response = await self._get(
            f"/projects/{projectAccession}/files/all",
            params={"filenameFilter": filenameFilter},
        )
        return [PRIDEFile.model_validate(item) for item in response.json()]

    async def getCountOfProjectFiles(self, projectAccession: str) -> int:
        response = await self._get(f"/projects/{projectAccession}/files/count")
        return int(response.text)

    async def getSDRFFiles(self, projectAccession: str) -> List[str]:
        response = await self._get(f"/files/sdrf/{projectAccession}")
        return response.json()

    async def getCountOfFilesByType(self, projectAccession: str) -> Dict[str, Any]:
        response = await self._get(f"/files/getCountOfFilesByType/{projectAccession}")
        return response.json()

    async def getCountOfAllFiles(self) -> int:
        response = await self._get("/files/count")
        return int(response.text)

    async def getFileChecksums(self, projectAccession: str) -> str:
        response = await self._get(f"/files/checksum/{projectAccession}")
        return response.text

    # ── Proteins ─────────────────────────────────────────────────────────

    async def getProteinByAccession(self, accession: str) -> PRIDEProjectsByProtein:
        response = await self._get(f"/proteins/{accession}")
        return PRIDEProjectsByProtein.model_validate(response.json())

    async def searchProteins(
        self, accession: str
    ) -> List[PRIDEProjectsByProteinWrapper]:
        response = await self._get("/proteins/search", params={"accession": accession})
        return [
            PRIDEProjectsByProteinWrapper.model_validate(item)
            for item in response.json()
        ]

    async def getAllProteinAccessions(
        self, pageSize: int = 100, pageNumber: int = 0
    ) -> ProteinAccessionsPageResponse:
        response = await self._get(
            "/proteins/allAccessions",
            params={"pageSize": pageSize, "pageNumber": pageNumber},
        )
        return ProteinAccessionsPageResponse.model_validate(response.json())

    # ── Stats ────────────────────────────────────────────────────────────

    async def getStats(self, name: str) -> Any:
        response = await self._get(f"/stats/{name}")
        return response.json()

    async def getSubmittedDataStats(self) -> Any:
        response = await self._get("/stats/submitted-data")
        return response.json()

    async def getSubmissionsMonthlyTSV(self) -> str:
        response = await self._get("/stats/submissions-monthly-tsv")
        return response.text

    async def getSubmissionsMonthly(self) -> Any:
        response = await self._get("/stats/submissions-monthly")
        return response.json()

    # ── Affinity Purification Projects ───────────────────────────────────

    async def getAPProject(self, accession: str) -> PRIDEAPProject:
        response = await self._get(f"/pride-ap/{accession}")
        return PRIDEAPProject.model_validate(response.json())

    async def searchAPProjects(self, query: PRIDEAPSearchQuery) -> List[PRIDEAPProject]:
        response = await self._get(
            "/pride-ap/search/projects", params=query.model_dump()
        )
        return [PRIDEAPProject.model_validate(item) for item in response.json()]

    async def searchAPProteins(self, query: PRIDEAPProteinSearchQuery) -> List[Protein]:
        response = await self._get(
            "/pride-ap/search/proteins", params=query.model_dump()
        )
        return [Protein.model_validate(item) for item in response.json()]
