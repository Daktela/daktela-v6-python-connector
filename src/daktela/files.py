"""Downloaded and uploaded files."""

import os
from dataclasses import dataclass, field
from email.message import Message
from email.utils import collapse_rfc2231_value
from pathlib import Path
from typing import Dict, Optional, Union

# Characters Windows does not allow in file names. ":" would also turn
# "C:name" into a drive-relative path and "name:stream" into an NTFS stream.
_FORBIDDEN_FILENAME_CHARACTERS = frozenset('<>:"|?*')
# Windows device names, reserved with any extension.
_RESERVED_FILENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"{device}{index}" for device in ("COM", "LPT") for index in "123456789¹²³"}
)


def _filename_from_disposition(value: Optional[str]) -> Optional[str]:
    """Return the file name of a ``Content-Disposition`` header.

    Supports both ``filename="..."`` and the RFC 6266 ``filename*=UTF-8''...``
    form, which takes precedence.
    """
    if not value:
        return None
    message = Message()
    message["Content-Disposition"] = value
    plain: Optional[str] = None
    params = message.get_params(header="content-disposition") or []
    for key, param in params[1:]:
        if key.lower() != "filename":
            continue
        if isinstance(param, tuple):
            # filename*=charset'language'value, decoded by the email package
            return collapse_rfc2231_value(param) or None
        plain = plain or param
    return plain or None


@dataclass(frozen=True)
class DaktelaFile:
    """A file downloaded from a Daktela instance.

    Attributes:
        content: The file content
        filename: File name suggested by the server, if any. It may come from
            whoever sent the file, so use :attr:`safe_filename` to build a path.
        content_type: Media type reported by the server, if any
        status_code: HTTP status code (206 for a partial range)
    """

    content: bytes = field(repr=False)
    filename: Optional[str] = None
    content_type: Optional[str] = None
    status_code: int = 200

    @property
    def size(self) -> int:
        """Return the content size in bytes."""
        return len(self.content)

    @property
    def safe_filename(self) -> Optional[str]:
        """Return the server's file name reduced to a safe base name, or ``None``.

        Directory parts (``/`` and ``\\``), control characters, and leading and
        trailing dots and spaces are removed, the characters Windows forbids
        (``<>:"|?*``) are replaced with ``_``, and a Windows device name such as
        ``NUL`` or ``con.txt`` gets a ``_`` prefix. So
        ``directory / file.safe_filename`` names a regular file inside
        ``directory`` on every platform. ``None`` means nothing usable is left.
        """
        if not self.filename:
            return None
        name = self.filename.replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(
            "_" if char in _FORBIDDEN_FILENAME_CHARACTERS else char
            for char in name
            if char.isprintable()
        ).strip(" .")
        if name.partition(".")[0].rstrip(" ").upper() in _RESERVED_FILENAMES:
            name = f"_{name}"
        return name or None

    def save(self, path: Union[str, "os.PathLike[str]"]) -> Path:
        """Write the content to ``path`` and return it as a :class:`Path`."""
        target = Path(path)
        target.write_bytes(self.content)
        return target


@dataclass(frozen=True)
class DaktelaUploadedFile:
    """A file uploaded to the instance's temporary storage.

    Reference it once in the payload of the entity that uses it (for example an
    email activity or a template); the server removes unused uploads after a
    short time.

    Attributes:
        name: File name assigned by the server
        title: Original file name, with its extension
    """

    name: str
    title: str

    def as_dict(self) -> Dict[str, str]:
        """Return the file object the API expects: ``{"name": ..., "title": ...}``."""
        return {"name": self.name, "title": self.title}
