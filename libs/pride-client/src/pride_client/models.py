from typing import List, Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class CvParam(BaseModel):
    """Controlled vocabulary parameter used in PRIDE metadata."""
    type_: str = Field(alias="@type")
    cvLabel: str
    accession: str
    name: str


class Person(BaseModel):
    """Person information for submitters and lab PIs."""
    title: str
    firstName: str
    lastName: str
    identifier: str
    affiliation: str
    email: str
    country: str
    orcid: str
    name: str
    id: str


class CvParamValue(BaseModel):
    """Controlled vocabulary parameter with value."""
    cvLabel: str
    accession: str
    name: str


class Tuple(BaseModel):
    """Tuple structure for sample attributes."""
    type_: str = Field(alias="@type")
    key: CvParamValue
    value: List[CvParamValue]


class PRIDE_Project(BaseModel):
    """PRIDE project detail model for ``/projects/{id}`` endpoint.

    Uses structured CvParam / Person / Tuple objects as returned by the
    detail API.
    """

    model_config = ConfigDict(extra="allow")

    accession: str
    title: str
    additionalAttributes: List[Any] = Field(default_factory=list)
    projectDescription: str
    sampleProcessingProtocol: str
    dataProcessingProtocol: str
    projectTags: List[Any] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    doi: str = ""
    submissionType: str
    license: Optional[str] = None
    submissionDate: str
    publicationDate: str
    submitters: List[Person] = Field(default_factory=list)
    labPIs: List[Person] = Field(default_factory=list)
    instruments: List[CvParam] = Field(default_factory=list)
    softwares: List[CvParam] = Field(default_factory=list)
    experimentTypes: List[CvParam] = Field(default_factory=list)
    quantificationMethods: List[Any] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    sampleAttributes: List[Tuple] = Field(default_factory=list)
    organisms: List[CvParam] = Field(default_factory=list)
    organismParts: List[Any] = Field(default_factory=list)
    diseases: List[Any] = Field(default_factory=list)
    references: List[Any] = Field(default_factory=list)
    identifiedPTMStrings: List[CvParam] = Field(default_factory=list)
    totalFileDownloads: int = 0


class PRIDE_Project_Summary(BaseModel):
    """PRIDE project summary model for ``/search/projects`` endpoint.

    The search API returns flat strings for submitters, instruments,
    experimentTypes, organisms, etc. — not the structured objects used
    by the detail endpoint.
    """

    model_config = ConfigDict(extra="allow")

    accession: str
    title: str
    projectDescription: str = ""
    sampleProcessingProtocol: str = ""
    dataProcessingProtocol: str = ""
    projectTags: List[Any] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    doi: str = ""
    submissionType: str = ""
    submissionDate: str = ""
    publicationDate: str = ""
    updatedDate: str = ""
    submitters: List[str] = Field(default_factory=list)
    labPIs: List[str] = Field(default_factory=list)
    affiliations: List[str] = Field(default_factory=list)
    instruments: List[str] = Field(default_factory=list)
    softwares: List[str] = Field(default_factory=list)
    experimentTypes: List[str] = Field(default_factory=list)
    quantificationMethods: List[str] = Field(default_factory=list)
    sampleAttributes: List[str] = Field(default_factory=list)
    organisms: List[str] = Field(default_factory=list)
    organismsPart: List[str] = Field(default_factory=list)
    diseases: List[str] = Field(default_factory=list)
    references: List[Any] = Field(default_factory=list)
    downloadCount: int = 0
    avgDownloadsPerFile: float = 0.0
    percentile: int = 0
    projectFileNames: List[str] = Field(default_factory=list)
    sdrf: str = ""


class PRIDESearchQuery(BaseModel):
    keyword: str
    filter: str
    pageSize: int = Field(default=100)
    page: int = Field(default=0)
    dateGap: str = Field(default='dateGap')
    sortDirection: Literal['DESC', 'ASC'] = Field(default='DESC')
    sortFields: Literal['submissionDate'] = Field(default='submissionDate')

class PRIDEProjectDownloadLinks(BaseModel):
    ftp: str
    globus: str