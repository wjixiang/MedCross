from __future__ import annotations

import pandas as pd
from tcia_utils import nbia


def _to_df(result: object) -> pd.DataFrame:
    """Normalize tcia_utils output (list[dict] or DataFrame) to DataFrame."""
    if isinstance(result, pd.DataFrame):
        return result
    if isinstance(result, list):
        if not result:
            return pd.DataFrame()
        return pd.DataFrame(result)
    return pd.DataFrame()


class TCIAApiClient:
    """Thin wrapper around tcia_utils.nbia functions.

    All query methods return pandas DataFrames for consistent CLI output.
    """

    # ---- Collections ----

    def get_collections(self) -> pd.DataFrame:
        return _to_df(nbia.getCollections())

    def get_collection_descriptions(self) -> pd.DataFrame:
        return _to_df(nbia.getCollectionDescriptions(removeHtml=True))

    def get_collection_patient_counts(self) -> pd.DataFrame:
        return _to_df(nbia.getCollectionPatientCounts())

    # ---- Patients ----

    def get_patients(self, collection: str) -> pd.DataFrame:
        return _to_df(nbia.getPatient(collection=collection))

    def get_patients_by_modality(self, collection: str, modality: str) -> pd.DataFrame:
        return _to_df(nbia.getPatientByCollectionAndModality(collection=collection, modality=modality))

    def get_new_patients(self, collection: str, date: str) -> pd.DataFrame:
        return _to_df(nbia.getNewPatientsInCollection(collection=collection, date=date))

    # ---- Studies ----

    def get_studies(self, collection: str, patient_id: str = "") -> pd.DataFrame:
        return _to_df(nbia.getStudy(collection=collection, patientId=patient_id))

    # ---- Series ----

    def get_series(
        self,
        collection: str = "",
        patient_id: str = "",
        study_uid: str = "",
        series_uid: str = "",
        modality: str = "",
        body_part: str = "",
        manufacturer: str = "",
        model: str = "",
    ) -> pd.DataFrame:
        return _to_df(nbia.getSeries(
            collection=collection,
            patientId=patient_id,
            studyUid=study_uid,
            seriesUid=series_uid,
            modality=modality,
            bodyPart=body_part,
            manufacturer=manufacturer,
            manufacturerModel=model,
        ))

    def get_series_size(self, series_uid: str) -> pd.DataFrame:
        return _to_df(nbia.getSeriesSize(seriesUid=series_uid))

    def get_series_meta(self, series_uid: str) -> pd.DataFrame:
        return _to_df(nbia.getSeriesMetaData(seriesUid=series_uid))

    def get_sop_instance_uids(self, series_uid: str) -> pd.DataFrame:
        return _to_df(nbia.getSopInstanceUids(seriesUid=series_uid))

    def get_updated_series(self, date: str) -> pd.DataFrame:
        return _to_df(nbia.getUpdatedSeries(date=date))

    # ---- Modality / BodyPart / Manufacturer ----

    def get_modalities(self, collection: str = "", body_part: str = "") -> pd.DataFrame:
        return _to_df(nbia.getModality(collection=collection, bodyPart=body_part))

    def get_body_parts(self, collection: str = "", modality: str = "") -> pd.DataFrame:
        return _to_df(nbia.getBodyPart(collection=collection, modality=modality))

    def get_manufacturers(self, collection: str = "") -> pd.DataFrame:
        return _to_df(nbia.getManufacturer(collection=collection))

    # ---- Download ----

    def download_series(
        self,
        series_data: str | list[str],
        path: str = "tciaDownload",
        as_zip: bool = False,
        with_hash: bool = False,
        max_workers: int = 10,
        number: int = 0,
    ) -> None:
        nbia.downloadSeries(
            series_data=series_data,
            path=path,
            as_zip=as_zip,
            hash="yes" if with_hash else "",
            max_workers=max_workers,
            number=number,
        )

    def download_image(self, series_uid: str, sop_uid: str, path: str = "") -> None:
        nbia.downloadImage(seriesUID=series_uid, sopUID=sop_uid, path=path)

    # ---- Search ----

    def simple_search(
        self,
        collections: list[str] | None = None,
        modalities: list[str] | None = None,
        body_parts: list[str] | None = None,
        manufacturers: list[str] | None = None,
        from_date: str = "",
        to_date: str = "",
        patients: list[str] | None = None,
        min_studies: int = 0,
        limit: int = 10,
        offset: int = 0,
    ) -> pd.DataFrame:
        return _to_df(nbia.getSimpleSearch(
            collections=collections or [],
            modalities=modalities or [],
            bodyParts=body_parts or [],
            manufacturers=manufacturers or [],
            fromDate=from_date,
            toDate=to_date,
            patients=patients or [],
            minStudies=min_studies,
            start=offset,
            size=limit,
        ))

    # ---- Reports ----

    def report_doi_summary(self, series_data: str | list[str]) -> pd.DataFrame:
        return _to_df(nbia.reportDoiSummary(series_data=series_data))

    def report_collection_summary(self, collection: str) -> pd.DataFrame:
        df = _to_df(nbia.getSeries(collection=collection))
        return _to_df(nbia.reportCollectionSummary(series_data=df))

    # ---- DICOM ----

    def get_dicom_tags(self, series_uid: str) -> pd.DataFrame:
        return _to_df(nbia.getDicomTags(seriesUid=series_uid))

    def get_seg_ref_series(self, series_uid: str) -> pd.DataFrame:
        return _to_df(nbia.getSegRefSeries(uid=series_uid))
