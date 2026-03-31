from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CvParam(BaseModel):
    cvLabel: str
    accession: str
    name: str
    value: str = ""


class CvParamTyped(BaseModel):
    type_: str = Field(alias="@type")
    cvLabel: str
    accession: str
    name: str


class CvParamValue(BaseModel):
    cvLabel: str
    accession: str
    name: str


class Person(BaseModel):
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


class Tuple(BaseModel):
    type_: str = Field(alias="@type")
    key: CvParamValue
    value: List[CvParamValue]


class YearlyDownload(BaseModel):
    year: str
    count: int


class PRIDE_Project(BaseModel):
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
    keyword: str = ""
    filter: str = ""
    pageSize: int = Field(default=100)
    page: int = Field(default=0)
    dateGap: str = Field(default="")
    sortDirection: Literal["DESC", "ASC"] = Field(default="DESC")
    sortFields: str = Field(default="submissionDate")


class PRIDEProjectDownloadLinks(BaseModel):
    ftp: str
    globus: str


class PRIDEFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    projectAccessions: List[str] = Field(default_factory=list)
    analysisAccessions: List[str] = Field(default_factory=list)
    accession: str
    fileCategory: Optional[CvParam] = None
    checksum: str = ""
    publicFileLocations: List[CvParam] = Field(default_factory=list)
    fileSizeBytes: int = 0
    fileExtension: str = ""
    fileName: str = ""
    compress: bool = False
    submissionDate: Optional[datetime] = None
    publicationDate: Optional[datetime] = None
    updatedDate: Optional[datetime] = None
    additionalAttributes: List[CvParam] = Field(default_factory=list)
    totalDownloads: int = 0


class PRIDEProjectMetadata(BaseModel):
    accession: str
    title: str
    submissionType: str = ""
    description: str = ""
    sampleProcessingProtocol: str = ""
    dataProcessingProtocol: str = ""


class PRIDEProjectsByProtein(BaseModel):
    proteinAccession: str
    projects: List[str] = Field(default_factory=list)


class PRIDEProjectsByProteinWrapper(BaseModel):
    id: str = ""
    proteinAccession: str = ""
    projects: List[str] = Field(default_factory=list)


class ProteinAccessionsPageResponse(BaseModel):
    accessions: List[str] = Field(default_factory=list)
    totalElements: int = 0
    pageNumber: int = 0
    pageSize: int = 100
    totalPages: int = 0


class Protein(BaseModel):
    proteinAccession: str = ""
    proteinName: str = ""
    gene: str = ""
    projectCount: int = 0


class PRIDEAPProject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    accession: str
    title: str
    projectDescription: str = ""
    additionalAttributes: str = ""
    dataProcessingProtocol: str = ""
    sampleProcessingProtocol: str = ""
    projectTags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    doi: str = ""
    otherOmicsLinks: List[str] = Field(default_factory=list)
    submissionType: str = ""
    publicationDate: str = ""
    updatedDate: str = ""
    submissionDate: str = ""
    downloadCount: int = 0
    avgDownloadsPerFile: float = 0.0
    percentile: int = 0
    yearlyDownloads: List[YearlyDownload] = Field(default_factory=list)
    submitters: List[str] = Field(default_factory=list)
    labPIs: List[str] = Field(default_factory=list)
    affiliations: List[str] = Field(default_factory=list)
    instruments: List[str] = Field(default_factory=list)
    softwares: List[str] = Field(default_factory=list)
    quantificationMethods: List[str] = Field(default_factory=list)
    allCountries: List[str] = Field(default_factory=list)
    experimentalFactors: List[str] = Field(default_factory=list)
    experimentalFactorsFacet: List[str] = Field(default_factory=list)
    sampleAttributes: List[str] = Field(default_factory=list)
    organisms: List[str] = Field(default_factory=list)
    organismsPart: List[str] = Field(default_factory=list)
    diseases: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    experimentTypes: List[str] = Field(default_factory=list)
    sdrf: str = ""
    proteinIdentifications: List[str] = Field(default_factory=list)
    peptideSequences: str = ""
    identifiedPtmStrings: List[str] = Field(default_factory=list)
    projectFileNames: List[str] = Field(default_factory=list)
    suggestField: List[str] = Field(default_factory=list)
    prideArchiveType: str = ""
    score: float = 0.0
    highlights: Dict[str, List[str]] = Field(default_factory=dict)
    proteins: List[Protein] = Field(default_factory=list)
    noOfProteins: int = 0
    noOfSamples: int = 0


class PRIDEFacetQuery(BaseModel):
    keyword: str = ""
    filter: str = ""
    facetPageSize: int = Field(default=100)
    facetPage: int = Field(default=0)
    dateGap: str = Field(default="")


class PRIDEAPSearchQuery(BaseModel):
    keyword: str = ""
    filter: str = ""
    pageSize: int = Field(default=100)
    page: int = Field(default=0)
    dateGap: str = Field(default="")
    sortDirection: Literal["DESC", "ASC"] = Field(default="DESC")
    sortFields: str = Field(default="submissionDate")


class PRIDEAPProteinSearchQuery(BaseModel):
    projectAccession: str
    keyword: str = ""
    pageSize: int = Field(default=100)
    page: int = Field(default=0)
    sortField: str = Field(default="accession")
    sortDirection: Literal["DESC", "ASC"] = Field(default="ASC")
