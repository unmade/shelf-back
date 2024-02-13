from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self

from aiosmtplib import SMTP

if TYPE_CHECKING:
    from email.message import EmailMessage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from app.config import MailSMTPConfig

__all__ = [
    "SMTPEmailBackend",
]


class SMTPEmailBackend:
    __slots__ = ["smtp", "_stack"]

    def __init__(self, config: MailSMTPConfig) -> None:
        self.smtp = SMTP(
            hostname=config.smtp_hostname,
            port=config.smtp_port,
            username=config.smtp_username,
            password=config.smtp_password,
            use_tls=config.smtp_use_tls,
        )
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.smtp)  # type: ignore[arg-type]
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._stack.aclose()

    async def send(self, message: EmailMessage | MIMEText | MIMEMultipart) -> None:
        await self.smtp.send_message(message)
