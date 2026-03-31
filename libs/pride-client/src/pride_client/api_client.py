from typing import List, Optional
import httpx
from pydantic import BaseModel, Field, ValidationError
from .models import PRIDE_Project, PRIDE_Project_Summary, PRIDEProjectDownloadLinks, PRIDESearchQuery


class PRIDE_API_Client_Config(BaseModel):
    """Configuration for PRIDE API client."""
    baseUrl: str
    timeout: int = Field(default=30, description="Request timeout in seconds")


defaultPRIDEApiClientConfig = PRIDE_API_Client_Config(
    baseUrl='https://www.ebi.ac.uk/pride/ws/archive/v3'
)


class API_Client:
    """Client for interacting with the PRIDE API."""
    
    config: PRIDE_API_Client_Config
    
    def __init__(self, config: Optional[PRIDE_API_Client_Config] = None) -> None:
        """Initialize the API client with optional configuration.
        
        Args:
            config: Configuration for the API client. If None, uses default config.
        """
        self.config = config or defaultPRIDEApiClientConfig

    async def retrieveProjectById(self, projectId: str) -> PRIDE_Project:
        """Retrieve a PRIDE project by its accession ID asynchronously.
        
        Args:
            projectId: The PRIDE project accession ID (e.g., 'PXD046193')
            
        Returns:
            PRIDE_Project: The parsed project data
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValidationError: If the response data cannot be validated against PRIDE_Project model
        """
        requestUrl = f"{self.config.baseUrl}/projects/{projectId}"
        
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(requestUrl)
            response.raise_for_status()
            data = response.json()
            
        # Use Pydantic's model_validate for safe parsing with full validation
        try:
            return PRIDE_Project.model_validate(data)
        except ValidationError as e:
            # Provide detailed validation error information
            error_details = e.errors()
            raise ValidationError(
                f"Failed to validate PRIDE project data for '{projectId}'. "
                f"Validation errors: {error_details}",
                PRIDE_Project,
                data
            ) from e
        
    async def searchProjects(self, query: PRIDESearchQuery) -> tuple[List[PRIDE_Project_Summary], int]:
        """Search PRIDE projects by keyword with filtering and pagination.

        Args:
            query: Search query parameters including keyword, filter, page size, etc.

        Returns:
            Tuple of (list of PRIDE_Project_Summary, total record count)

        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValidationError: If any project data cannot be validated
        """
        requestUrl = f"{self.config.baseUrl}/search/projects"
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(requestUrl, params=query.model_dump())
            response.raise_for_status()
            total = int(response.headers.get("total_records", 0))
            data = response.json()

        try:
            return [PRIDE_Project_Summary.model_validate(item) for item in data], total
        except Exception as e:
            raise e
    
    async def downloadProject(self, accession: str) -> PRIDEProjectDownloadLinks: 
        requestUrl = f"{self.config.baseUrl}/projects/files-path/{accession}"

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(requestUrl)
            response.raise_for_status()
            data = response.json()
        
        try:
            return PRIDEProjectDownloadLinks.model_validate(data)
        except Exception as e:
            raise e

