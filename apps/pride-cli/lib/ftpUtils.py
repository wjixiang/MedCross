from __future__ import annotations

import ftplib
from pathlib import Path
from urllib.parse import urlparse

from rich.progress import Progress


def parse_ftp_url(url: str) -> tuple[str, str]:
    """Parse an FTP URL into (host, path)."""
    parsed = urlparse(url)
    return parsed.hostname or "", parsed.path


def download_file(
    ftp: ftplib.FTP,
    remote_path: str,
    local_path: Path,
    progress: Progress,
    task_id,
) -> None:
    """Download a single file with progress tracking."""
    size = ftp.size(remote_path)
    progress.update(
        task_id, total=size or 0, description=remote_path.rsplit("/", 1)[-1]
    )

    with open(local_path, "wb") as f:
        ftp.retrbinary(
            f"RETR {remote_path}",
            callback=lambda data: (
                f.write(data),
                progress.update(task_id, advance=len(data)),
            ),
            blocksize=8192,
        )


def download_dir(
    ftp: ftplib.FTP,
    remote_dir: str,
    local_dir: Path,
    progress: Progress,
    task_id: int | None = None,
) -> None:
    """Recursively download all files from a remote FTP directory."""
    local_dir.mkdir(parents=True, exist_ok=True)

    entries: list[str] = []
    ftp.dir(remote_dir, entries.append)  # type: ignore[arg-type]

    for entry in entries:
        # FTP dir output format: "drwxr-xr-x 2 owner group 4096 Jan 01 12:00 name"
        parts = entry.split()
        if len(parts) < 9:
            continue
        name = " ".join(parts[8:])
        is_dir = entry.startswith("d")
        remote_path = f"{remote_dir}/{name}"
        local_path = local_dir / name

        if is_dir:
            download_dir(ftp, remote_path, local_path, progress, task_id)
        else:
            child_task = progress.add_task(name, total=0)
            download_file(ftp, remote_path, local_path, progress, child_task)
            progress.update(child_task, description=f"[green]{name}[/green]")
