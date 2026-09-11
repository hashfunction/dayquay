import errno
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from rednotebook import atomic, backup, storage


MANIFEST_MAX_BYTES = 8 * 1024 * 1024
COPY_CHUNK_SIZE = 1024 * 1024
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")
QUOTED_LOCAL_TARGET_PATTERN = re.compile(
    r'""(?P<target>[^"\r\n]+?)""(?P<extension>\.(?:png|jpe?g|gif|eps|bmp|svg))?',
    flags=re.IGNORECASE,
)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class InvalidBackup(ValueError):
    pass


@dataclass(frozen=True)
class RestoreLimits:
    max_entries: int = 100_000
    max_total_bytes: int = 20 * 1024 * 1024 * 1024
    max_member_bytes: int = 16 * 1024 * 1024 * 1024
    max_compression_ratio: float = 200.0


DEFAULT_LIMITS = RestoreLimits()


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class BackupInspection:
    archive_path: str
    archive_sha256: str
    created_at: str
    entries: tuple
    file_count: int
    total_bytes: int
    limits: RestoreLimits


@dataclass(frozen=True)
class JournalValidation:
    month_count: int
    attachment_count: int
    referenced_attachment_count: int = 0


@dataclass(frozen=True)
class RestoreResult:
    destination: str
    file_count: int
    total_bytes: int
    journal: JournalValidation


def _hash_stream(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(COPY_CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest()


def _hash_path(path):
    with path.open("rb") as stream:
        return _hash_stream(stream)


def _validated_member_path(name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise InvalidBackup(f"Backup contains unsafe path: {name!r}")
    if name.startswith("/") or WINDOWS_DRIVE_PATTERN.match(name):
        raise InvalidBackup(f"Backup contains unsafe path: {name!r}")
    raw_parts = name.split("/")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in raw_parts):
        raise InvalidBackup(f"Backup contains unsafe path: {name!r}")
    for part in raw_parts:
        stem = part.split(".", 1)[0].upper()
        if ":" in part or part.endswith((" ", ".")) or stem in WINDOWS_RESERVED_NAMES:
            raise InvalidBackup(f"Backup contains unsafe path: {name!r}")
    return path


def _windows_path_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def _validate_zip_info(info, limits):
    _validated_member_path(info.filename)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise InvalidBackup(f"Backup contains a symbolic link: {info.filename}")
    if info.is_dir():
        raise InvalidBackup(f"Backup contains an unexpected directory member: {info.filename}")
    if info.flag_bits & 0x1:
        raise InvalidBackup(f"Backup contains an encrypted member: {info.filename}")
    if info.file_size < 0 or info.file_size > limits.max_member_bytes:
        raise InvalidBackup(f"Backup member exceeds size limit: {info.filename}")
    if info.file_size:
        if info.compress_size <= 0:
            raise InvalidBackup(f"Backup member has invalid compressed size: {info.filename}")
        if info.file_size / info.compress_size > limits.max_compression_ratio:
            raise InvalidBackup(f"Backup member exceeds compression ratio: {info.filename}")


def _parse_manifest(raw, data_infos):
    if len(raw) > MANIFEST_MAX_BYTES:
        raise InvalidBackup("Backup manifest exceeds size limit")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidBackup(f"Backup manifest is invalid JSON: {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "created_at",
        "entries",
        "format",
        "version",
    }:
        raise InvalidBackup("Backup manifest has an invalid schema")
    if manifest["format"] != "dayquay-backup" or manifest["version"] != 1:
        raise InvalidBackup("Backup manifest format or version is unsupported")
    if not isinstance(manifest["created_at"], str) or not manifest["created_at"]:
        raise InvalidBackup("Backup manifest creation time is invalid")
    raw_entries = manifest["entries"]
    if not isinstance(raw_entries, list) or len(raw_entries) != len(data_infos):
        raise InvalidBackup("Backup manifest does not cover every archive member")
    entries = []
    for item in raw_entries:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise InvalidBackup("Backup manifest entry has an invalid schema")
        path = item["path"]
        size = item["size"]
        digest = item["sha256"]
        _validated_member_path(path)
        if type(size) is not int or size < 0:
            raise InvalidBackup(f"Backup manifest size is invalid: {path!r}")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise InvalidBackup(f"Backup manifest checksum is invalid: {path!r}")
        entries.append(ArchiveEntry(path=path, size=size, sha256=digest))
    if [entry.path for entry in entries] != sorted(entry.path for entry in entries):
        raise InvalidBackup("Backup manifest entries are not sorted")
    info_by_name = {info.filename: info for info in data_infos}
    if set(info_by_name) != {entry.path for entry in entries}:
        raise InvalidBackup("Backup manifest paths do not match archive members")
    for entry in entries:
        if info_by_name[entry.path].file_size != entry.size:
            raise InvalidBackup(f"Backup manifest size mismatch: {entry.path}")
    return manifest, tuple(entries)


def inspect_backup(path, limits=DEFAULT_LIMITS, *, verify_hashes=True):
    archive_path = Path(path)
    if archive_path.is_symlink():
        raise InvalidBackup(f"Backup path is a symbolic link: {archive_path}")
    try:
        archive_path = archive_path.resolve(strict=True)
        mode = archive_path.stat().st_mode
    except OSError as exc:
        raise InvalidBackup(f"Backup cannot be read: {path}") from exc
    if not stat.S_ISREG(mode):
        raise InvalidBackup(f"Backup is not a regular file: {archive_path}")
    archive_digest = _hash_path(archive_path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_entries + 1:
                raise InvalidBackup("Backup exceeds entry limit")
            seen = set()
            seen_windows = set()
            for info in infos:
                _validate_zip_info(info, limits)
                windows_name = _windows_path_key(info.filename)
                if info.filename in seen or windows_name in seen_windows:
                    raise InvalidBackup(f"Backup contains duplicate path: {info.filename}")
                seen.add(info.filename)
                seen_windows.add(windows_name)
            manifests = [info for info in infos if info.filename == backup.MANIFEST_NAME]
            if len(manifests) != 1:
                raise InvalidBackup("Backup must contain exactly one manifest")
            if manifests[0].file_size > MANIFEST_MAX_BYTES:
                raise InvalidBackup("Backup manifest exceeds size limit")
            data_infos = [info for info in infos if info.filename != backup.MANIFEST_NAME]
            total_bytes = sum(info.file_size for info in data_infos)
            if total_bytes > limits.max_total_bytes:
                raise InvalidBackup("Backup exceeds total uncompressed size limit")
            manifest, entries = _parse_manifest(archive.read(manifests[0]), data_infos)
            if verify_hashes:
                for entry in entries:
                    with archive.open(entry.path) as stream:
                        digest = _hash_stream(stream)
                    if digest != entry.sha256:
                        raise InvalidBackup(f"Backup checksum mismatch: {entry.path}")
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, InvalidBackup):
            raise
        raise InvalidBackup(f"Backup ZIP is unreadable: {exc}") from exc
    return BackupInspection(
        archive_path=str(archive_path),
        archive_sha256=archive_digest,
        created_at=manifest["created_at"],
        entries=entries,
        file_count=len(entries),
        total_bytes=total_bytes,
        limits=limits,
    )


def _local_attachment_targets(text):
    for match in QUOTED_LOCAL_TARGET_PATTERN.finditer(text):
        target = match.group("target")
        if extension := match.group("extension"):
            target += extension
        lowered = target.lower()
        if lowered.startswith(("http://", "https://", "ftp://", "irc://")):
            continue
        if lowered.startswith("file:///#") or re.fullmatch(r"\d{4}-\d{2}-\d{2}", target):
            continue
        if lowered.startswith("file://"):
            target = target[len("file://") :]
        elif "://" in target:
            continue
        yield urllib.parse.unquote(target)


def _validate_attachment_references(directory, months):
    referenced = set()
    for month in months.values():
        for day in month.days.values():
            for target in _local_attachment_targets(day.text):
                drive_candidate = target[1:] if target.startswith("/") else target
                if (
                    not target
                    or target.startswith("/")
                    or WINDOWS_DRIVE_PATTERN.match(drive_candidate)
                    or "\\" in target
                ):
                    raise InvalidBackup(
                        f"Journal contains an external local attachment that is not portable: {target}"
                    )
                parts = target.split("/")
                if any(part in ("", ".", "..") for part in parts):
                    raise InvalidBackup(
                        f"Journal contains an unsafe local attachment reference: {target}"
                    )
                candidate = directory.joinpath(*parts)
                try:
                    candidate.relative_to(directory)
                except ValueError as exc:
                    raise InvalidBackup(
                        f"Journal attachment escapes the portable journal: {target}"
                    ) from exc
                if candidate.is_symlink() or not candidate.is_file():
                    raise InvalidBackup(f"Journal referenced attachment is missing: {target}")
                referenced.add(candidate)
    return len(referenced)


def validate_journal_directory(path):
    directory = Path(path)
    if not directory.is_dir() or directory.is_symlink():
        raise InvalidBackup(f"Restored journal is not a real directory: {directory}")
    attachment_count = 0
    for item in directory.rglob("*"):
        if item.is_symlink():
            raise InvalidBackup(f"Restored journal contains a symbolic link: {item}")
        if not (item.is_file() or item.is_dir()):
            raise InvalidBackup(f"Restored journal contains an unsafe file: {item}")
        is_month = item.parent == directory and re.fullmatch(r"\d{4}-\d{2}\.txt", item.name)
        if item.is_file() and not is_month:
            attachment_count += 1
    try:
        months = storage.load_all_months_from_disk(directory, raise_on_error=True)
    except (storage.InvalidJournalData, OSError, ValueError) as exc:
        raise InvalidBackup(f"Restored journal data is invalid: {exc}") from exc
    referenced_attachment_count = _validate_attachment_references(directory, months)
    return JournalValidation(
        month_count=len(months),
        attachment_count=attachment_count,
        referenced_attachment_count=referenced_attachment_count,
    )


def _atomic_rename_directory_no_replace(source, destination):
    atomic.rename_directory_no_replace(source, destination)


def restore_backup(path, destination, inspection):
    requested_destination = Path(destination)
    if requested_destination.is_symlink():
        raise FileExistsError(
            errno.EEXIST, "Restore destination is a symbolic link", str(requested_destination)
        )
    destination = requested_destination.parent.resolve() / requested_destination.name
    parent = destination.parent
    if destination.exists():
        raise FileExistsError(errno.EEXIST, "Restore destination already exists", str(destination))
    if not parent.is_dir():
        raise InvalidBackup(f"Restore parent is not a directory: {parent}")
    current = inspect_backup(path, limits=inspection.limits, verify_hashes=True)
    if current.archive_sha256 != inspection.archive_sha256:
        raise InvalidBackup("Backup changed since inspection")
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.dayquay-", dir=parent))
    try:
        with zipfile.ZipFile(current.archive_path) as archive:
            for entry in current.entries:
                target = staging.joinpath(*PurePosixPath(entry.path).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with archive.open(entry.path) as source, target.open("xb") as output:
                    while chunk := source.read(COPY_CHUNK_SIZE):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if size != entry.size or digest.hexdigest() != entry.sha256:
                    raise InvalidBackup(f"Backup checksum mismatch during restore: {entry.path}")
        validation = validate_journal_directory(staging)
        _atomic_rename_directory_no_replace(staging, destination)
        return RestoreResult(
            destination=str(destination),
            file_count=current.file_count,
            total_bytes=current.total_bytes,
            journal=validation,
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)
