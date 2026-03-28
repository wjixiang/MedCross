import typer

from lib.commands import collections, patients, series, download, search, report, dicom

app = typer.Typer(
    name="tcia",
    help="TCIA medical imaging data fetcher — query and download from The Cancer Imaging Archive.",
    no_args_is_help=True,
)

app.add_typer(collections.app, name="collections")
app.add_typer(patients.app, name="patients")
app.add_typer(series.app, name="series")
app.add_typer(download.app, name="download")
app.add_typer(search.app, name="search")
app.add_typer(report.app, name="report")
app.add_typer(dicom.app, name="dicom")


if __name__ == "__main__":
    app()
