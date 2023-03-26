import uuid

from .content_metadata import ContentMetadata, Exif
from .file import File
from .fingerprint import Fingerprint
from .namespace import Namespace
from .shared_link import SharedLink

__all__ = [
    "SENTINEL_ID",
    "ContentMetadata",
    "Exif",
    "File",
    "Fingerprint",
    "Namespace",
    "SharedLink",
]

SENTINEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
