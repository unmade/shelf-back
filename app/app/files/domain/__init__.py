from __future__ import annotations

from .content import IFileContent
from .content_metadata import ContentMetadata, Exif
from .file import File, MountedFile
from .file_member import FileMember
from .file_pending_deletion import FilePendingDeletion
from .fingerprint import Fingerprint
from .mount import MountPoint
from .namespace import Namespace
from .path import AnyPath, Path
from .shared_link import SharedLink

__all__ = [
    "ContentMetadata",
    "Exif",
    "File",
    "FileMember",
    "FilePendingDeletion",
    "IFileContent",
    "MountedFile",
    "Fingerprint",
    "MountPoint",
    "Namespace",
    "AnyPath",
    "Path",
    "SharedLink",
]

type AnyFile = File | MountedFile
