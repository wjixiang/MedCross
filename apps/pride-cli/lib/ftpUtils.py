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
    resume: bool = True,
) -> None:
    """Download a single file with progress tracking, optionally resuming from existing local size."""
    remote_size = ftp.size(remote_path) or 0
    progress.update(
        task_id, total=remote_size, description=remote_path.rsplit("/", 1)[-1]
    )

    rest_offset = None
    mode = "wb"
    if resume and local_path.exists():
        local_size = local_path.stat().st_size
        if remote_size and local_size >= remote_size:
            progress.update(task_id, total=remote_size, completed=remote_size)
            return
        if 0 < local_size < remote_size:
            mode = "ab"
            rest_offset = local_size
            progress.update(task_id, completed=local_size)

    ftp.voidcmd("TYPE I")
    conn = ftp.transfercmd(f"RETR {remote_path}", rest=rest_offset)
    try:
        with open(local_path, mode) as f:
            while True:
                data = conn.recv(8192)
                if not data:
                    break
                f.write(data)
                progress.update(task_id, advance=len(data))
    finally:
        conn.close()
    old_timeout = ftp.sock.gettimeout() if ftp.sock else None
    if ftp.sock:
        ftp.sock.settimeout(None)
    try:
        ftp.voidresp()
    except (ftplib.error_temp, TimeoutError, OSError):
        pass
    finally:
        if ftp.sock and old_timeout is not None:
            ftp.sock.settimeout(old_timeout)


def download_dir(
    ftp: ftplib.FTP,
    remote_dir: str,
    local_dir: Path,
    progress: Progress,
    task_id: int | None = None,
    resume: bool = True,
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
            download_dir(ftp, remote_path, local_path, progress, task_id, resume)
        else:
            child_task = progress.add_task(name, total=0)
            download_file(ftp, remote_path, local_path, progress, child_task, resume)
            progress.update(child_task, description=f"[green]{name}[/green]")
