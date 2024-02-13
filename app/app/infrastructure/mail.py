from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from email.message import EmailMessage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText


class IMailBackend(Protocol):
    async def __aenter__(self) -> Self:
        raise NotImplementedError()  # pragma: no cover

    async def __aexit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError()  # pragma: no cover

    async def send(self, message: EmailMessage | MIMEText | MIMEMultipart) -> None:
        """Sends and email to given content."""
