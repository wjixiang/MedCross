import asyncio

from pride_client.api_client import API_Client, defaultPRIDEApiClientConfig
from pride_client.models import (
    PRIDEAPProteinSearchQuery,
    PRIDEFacetQuery,
    PRIDESearchQuery,
)

client = API_Client(defaultPRIDEApiClientConfig)


async def test_status():
    status = await client.getProjectStatus("PXD046193")
    assert status in ("PUBLIC", "PRIVATE"), f"Unexpected status: {status}"
    print(f"OK: status = {status}")


async def test_project_count():
    count = await client.getCountOfAllProjects()
    assert count > 0, "Project count should be > 0"
    print(f"OK: total projects = {count}")


async def test_search():
    query = PRIDESearchQuery(keyword="proteome", pageSize=2, page=0)
    results, total = await client.searchProjects(query)
    assert len(results) > 0, "Search should return results"
    print(f"OK: search returned {len(results)} results, total={total}")


async def test_retrieve():
    project = await client.retrieveProjectById("PXD046193")
    assert project.accession == "PXD046193"
    print(f"OK: project = {project.accession} - {project.title[:60]}")


async def test_autocomplete():
    suggestions = await client.autocomplete("proteome")
    assert isinstance(suggestions, list)
    print(f"OK: autocomplete returned {len(suggestions)} suggestions")


async def test_facets():
    facets = await client.getFacets(PRIDEFacetQuery(keyword="human", facetPageSize=3))
    assert isinstance(facets, dict)
    print(f"OK: facets has {len(facets)} categories")


async def test_download_links():
    links = await client.downloadProject("PXD046193")
    assert links.ftp != ""
    print(f"OK: ftp path = {links.ftp}")


async def test_protein_accessions():
    page = await client.getAllProteinAccessions(pageSize=3, pageNumber=0)
    assert page.totalElements > 0
    print(f"OK: protein accessions total = {page.totalElements}")


async def test_protein_by_accession():
    protein = await client.getProteinByAccession("P02768")
    assert protein.proteinAccession == "P02768"
    print(f"OK: protein P02768 found in {len(protein.projects)} projects")


async def test_ap_project():
    ap = await client.getAPProject("PRD000001")
    assert ap.accession == "PRD000001"
    print(f"OK: AP project = {ap.accession} - {ap.title[:60]}")


async def test_ap_proteins():
    query = PRIDEAPProteinSearchQuery(projectAccession="PRD000001", pageSize=3)
    proteins = await client.searchAPProteins(query)
    assert isinstance(proteins, list)
    print(f"OK: AP proteins returned {len(proteins)} results")


async def test_metadata():
    metadata = await client.getProjectsMetadata(page=0, pageSize=2)
    assert len(metadata) > 0
    print(f"OK: metadata returned {len(metadata)} results")


async def main():
    tests = [
        test_status,
        test_project_count,
        test_search,
        test_retrieve,
        test_autocomplete,
        test_facets,
        test_download_links,
        test_protein_accessions,
        test_protein_by_accession,
        test_ap_project,
        test_ap_proteins,
        test_metadata,
    ]
    for t in tests:
        try:
            await t()
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
    print("\nDone.")


asyncio.run(main())
