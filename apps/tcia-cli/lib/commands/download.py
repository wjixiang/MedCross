from __future__ import annotations

import os
import shutil
import threading

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from lib.output import print_error, print_success
from lib.tcia_api_client import TCIAApiClient

app = typer.Typer(help="Download DICOM images from TCIA")
console = Console()


@app.command("series")
def download_series(
    uids: list[str] = typer.Argument(help="Series Instance UID(s)"),
    output_dir: str = typer.Option("tciaDownload", "-o", "--output", help="Download directory"),
    zip_flag: bool = typer.Option(False, "--zip", help="Keep as ZIP (do not extract)"),
    hash_flag: bool = typer.Option(False, "--hash", help="Verify with MD5 hash"),
    workers: int = typer.Option(10, "--workers", "-w", help="Max parallel downloads"),
    number: int = typer.Option(0, "--number", "-n", help="Limit images per series (0 = all)"),
    organize: bool = typer.Option(True, "--organize/--no-organize", help="Organize into Collection/Patient/Series dirs and add .dcm extension"),
):
    """Download one or more DICOM series."""
    client = TCIAApiClient()

    # 过滤已存在的 series
    already_done = {uid for uid in uids if _series_exists(output_dir, uid)}
    pending_uids = [uid for uid in uids if uid not in already_done]
    if already_done:
        console.print(f"[dim]Skipping {len(already_done)} already downloaded series.[/dim]")
    if not pending_uids:
        print_success("All series already downloaded.")
        return

    console.print(f"[bold]Downloading {len(pending_uids)} series to {output_dir}...[/bold]")
    try:
        _download_with_progress(client, pending_uids, output_dir, zip_flag, hash_flag, workers, number)
        print_success("Download complete.")

        if organize and not zip_flag:
            meta_parts = []
            for uid in pending_uids:
                meta_df = client.get_series(series_uid=uid)
                if not meta_df.empty:
                    meta_parts.append(meta_df)
            if meta_parts:
                import pandas as pd
                meta_df = pd.concat(meta_parts, ignore_index=True)
                collections = meta_df["Collection"].dropna().unique()
                organized = 0
                for coll in collections:
                    coll_df = meta_df[meta_df["Collection"] == coll]
                    organized += _organize_series(output_dir, coll, coll_df)
                if organized:
                    print_success(f"Organized {organized} series into Collection/Patient/Series/ structure.")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("collection")
def download_collection(
    collection: str = typer.Option(..., "-c", "--collection", help="Collection name"),
    modality: str = typer.Option("", "-m", "--modality", help="Filter by modality (e.g. CT, MR)"),
    output_dir: str = typer.Option("tciaDownload", "-o", "--output", help="Download directory"),
    zip_flag: bool = typer.Option(False, "--zip", help="Keep as ZIP (do not extract)"),
    hash_flag: bool = typer.Option(False, "--hash", help="Verify with MD5 hash"),
    workers: int = typer.Option(10, "--workers", "-w", help="Max parallel downloads"),
    limit: int = typer.Option(0, "--limit", "-n", help="Max series to download (0 = all)"),
    organize: bool = typer.Option(True, "--organize/--no-organize", help="Organize into Collection/Patient/Series dirs and add .dcm extension"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List series to download without downloading"),
):
    """Download all series from a collection."""
    client = TCIAApiClient()
    df = client.get_series(collection=collection, modality=modality)
    if df.empty:
        print_error(f"No series found for collection '{collection}'.")
        raise typer.Exit(1)

    uids = df["SeriesInstanceUID"].tolist()
    if limit > 0:
        uids = uids[:limit]

    total_size = df["FileSize"].head(len(uids)).sum() if "FileSize" in df.columns else 0
    size_str = f" (~{_format_size(total_size)})" if total_size else ""

    console.print(f"[bold]Collection:[/bold] {collection}")
    console.print(f"[bold]Series:[/bold] {len(uids)}{size_str}")
    console.print(f"[bold]Output:[/bold] {output_dir}\n")

    if dry_run:
        from lib.output import print_table
        print_table(df.head(len(uids)), columns=["PatientID", "Modality", "BodyPartExamined", "ImageCount", "FileSize", "SeriesInstanceUID"], title="Series to download")
        return

    confirm = typer.confirm(f"Download {len(uids)} series?")
    if not confirm:
        raise typer.Abort()

    try:
        # 过滤已下载的 series（flat 目录 + organized 目录）
        already_flat = {uid for uid in uids if _series_exists(output_dir, uid)}
        already_organized = _series_exists_organized(output_dir, collection, df) if organize and not zip_flag else set()
        already_done = already_flat | already_organized
        pending_uids = [uid for uid in uids if uid not in already_done]

        if already_done:
            console.print(f"[dim]Skipping {len(already_done)} already downloaded series.[/dim]")
        if not pending_uids:
            print_success("All series already downloaded.")
            return

        console.print(f"[bold]To download:[/bold] {len(pending_uids)}\n")

        uid_sizes = dict(zip(df["SeriesInstanceUID"], df["FileSize"].fillna(0))) if "FileSize" in df.columns else {}
        pending_sizes = {uid: uid_sizes.get(uid, 0) for uid in pending_uids}
        _download_with_progress(client, pending_uids, output_dir, zip_flag, hash_flag, workers, uid_sizes=pending_sizes)
        print_success(f"Download complete. {len(pending_uids)} series saved to {output_dir}")

        if organize and not zip_flag:
            df_filtered = df[df["SeriesInstanceUID"].isin(pending_uids)]
            organized = _organize_series(output_dir, collection, df_filtered)
            if organized:
                print_success(f"Organized {organized} series into {collection}/Patient/Series/ structure.")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


def _count_done_bytes(uid_set: set[str], output_dir: str, uid_sizes: dict[str, float]) -> float:
    """统计输出目录中已完成 series 对应的字节数。"""
    done_bytes = 0.0
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            uid = name[:-4] if name.endswith(".zip") else name
            if uid in uid_set:
                done_bytes += uid_sizes.get(uid, 0)
    return done_bytes


def _download_with_progress(
    client: TCIAApiClient,
    uids: list[str],
    output_dir: str,
    zip_flag: bool,
    hash_flag: bool,
    workers: int,
    number: int = 0,
    uid_sizes: dict[str, float] | None = None,
) -> None:
    """在后台线程执行下载，主线程显示 Rich 进度条。"""
    uid_set = set(uids)
    uid_sizes = uid_sizes or {}
    has_sizes = bool(uid_sizes)
    total_bytes = sum(uid_sizes.get(uid, 0) for uid in uids)
    error: list[Exception] = []

    # 已存在的 series
    existing_bytes = _count_done_bytes(uid_set, output_dir, uid_sizes)
    existing_count = sum(1 for uid in uid_set if _series_exists(output_dir, uid))

    columns = [
        SpinnerColumn(),
        MofNCompleteColumn(),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
    ]
    if has_sizes:
        columns += [DownloadColumn(), TransferSpeedColumn()]
    columns += [TimeElapsedColumn(), TimeRemainingColumn()]

    with Progress(*columns, console=console) as progress:
        total = total_bytes if has_sizes else len(uids)
        initial = existing_bytes if has_sizes else existing_count
        task = progress.add_task("Downloading", total=total)
        progress.update(task, completed=initial)

        def _run():
            try:
                client.download_series(
                    series_data=uids,
                    path=output_dir,
                    as_zip=zip_flag,
                    with_hash=hash_flag,
                    max_workers=workers,
                    number=number,
                )
            except Exception as exc:
                error.append(exc)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while thread.is_alive():
            thread.join(timeout=1.0)
            if has_sizes:
                current_bytes = _count_done_bytes(uid_set, output_dir, uid_sizes)
                progress.update(task, completed=max(current_bytes, existing_bytes))
            else:
                current_count = sum(1 for uid in uid_set if _series_exists(output_dir, uid))
                progress.update(task, completed=max(current_count, existing_count))

        if error:
            raise error[0]

        # 最终同步
        if has_sizes:
            final_bytes = _count_done_bytes(uid_set, output_dir, uid_sizes)
            progress.update(task, completed=final_bytes)
        else:
            final_count = sum(1 for uid in uid_set if _series_exists(output_dir, uid))
            progress.update(task, completed=final_count)


def _series_exists(output_dir: str, uid: str) -> bool:
    """检查 series 目录或 zip 是否存在于 flat 目录中。"""
    if not os.path.isdir(output_dir):
        return False
    return uid in os.listdir(output_dir) or f"{uid}.zip" in os.listdir(output_dir)


def _series_exists_organized(output_dir: str, collection: str, series_df) -> set[str]:
    """检查哪些 series 已经在 organized 目录中存在。"""
    existing = set()
    if not os.path.isdir(output_dir):
        return existing
    for _, row in series_df.iterrows():
        uid = row["SeriesInstanceUID"]
        patient_id = str(row.get("PatientID", "unknown"))
        dst = os.path.join(output_dir, collection, patient_id, uid)
        if os.path.isdir(dst):
            existing.add(uid)
    return existing


def _format_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _organize_series(path: str, collection: str, series_df) -> int:
    """将平铺的 series 目录整理为 Collection/Patient/Series 结构，并添加 .dcm 后缀。返回整理的 series 数量。"""
    organized = 0
    for _, row in series_df.iterrows():
        uid = row["SeriesInstanceUID"]
        src = os.path.join(path, uid)
        if not os.path.isdir(src):
            continue

        patient_id = str(row.get("PatientID", "unknown"))
        dst_parent = os.path.join(path, collection, patient_id, uid)
        os.makedirs(dst_parent, exist_ok=True)

        for f in os.listdir(src):
            src_file = os.path.join(src, f)
            if os.path.isfile(src_file):
                new_name = f if f.endswith(".dcm") else f + ".dcm"
                shutil.move(src_file, os.path.join(dst_parent, new_name))

        shutil.rmtree(src)
        organized += 1

    return organized


@app.command("image")
def download_image(
    series_uid: str = typer.Argument(help="Series Instance UID"),
    sop_uid: str = typer.Argument(help="SOP Instance UID"),
    output_dir: str = typer.Option("", "-o", "--output", help="Output directory"),
):
    """Download a single DICOM image."""
    client = TCIAApiClient()
    try:
        client.download_image(series_uid=series_uid, sop_uid=sop_uid, path=output_dir)
        print_success("Image downloaded.")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)
