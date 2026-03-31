from __future__ import annotations

import asyncio
from typing import List, Tuple

from pride_client.api_client import API_Client, PRIDE_API_Client_Config
from pride_client.models import PRIDE_Project, PRIDE_Project_Summary, PRIDESearchQuery

_default_config = PRIDE_API_Client_Config(
    baseUrl="https://www.ebi.ac.uk/pride/ws/archive/v3"
)


def get_client(config: PRIDE_API_Client_Config | None = None) -> API_Client:
    """Get a PRIDE API client."""
    return API_Client(config or _default_config)


def search_projects(query: PRIDESearchQuery) -> Tuple[list[PRIDE_Project_Summary], int]:
    """Search projects (sync wrapper). Returns (results, total_count)."""
    return asyncio.run(get_client().searchProjects(query))


def get_project(accession: str) -> PRIDE_Project:
    """Get project details by accession (sync wrapper)."""
    return asyncio.run(get_client().retrieveProjectById(accession))
