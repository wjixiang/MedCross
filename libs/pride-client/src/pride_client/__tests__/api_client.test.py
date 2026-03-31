import asyncio

from pride_client.api_client import API_Client, defaultPRIDEApiClientConfig
from pride_client.models import PRIDESearchQuery

client = API_Client(defaultPRIDEApiClientConfig)

async def testRetrieveById():
    # Test retrieveProjectById
    getProjectByIdRes = await client.retrieveProjectById('PXD046193')
    print(f"Project: {getProjectByIdRes.accession} - {getProjectByIdRes.title}")

async def testSearchProjects():
    # Test searchProjects
    query = PRIDESearchQuery(keyword='proteome', filter='projectTitle', pageSize=5, page=0)
    results = await client.searchProjects(query)
    print(f"\nSearch 'proteome' found {len(results)} results:")
    
async def testGetDownloadLinks():
    result = await client.downloadProject("PXD064059")
    print(result)

asyncio.run(testGetDownloadLinks())