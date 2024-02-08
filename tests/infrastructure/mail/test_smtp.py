from __future__ import annotations

from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import pytest

from app.infrastructure.mail.smtp import SMTPEmailBackend

if TYPE_CHECKING:
    from tests.fixtures.infrastructure.smtp import SMTPDummyServer

pytestmark = [pytest.mark.anyio]


@pytest.fixture
def message() -> MIMEText:
    mime_message = MIMEText("Sent via aiosmtplib")
    mime_message["From"] = "root@localhost"
    mime_message["To"] = "somebody@example.com"
    mime_message["Subject"] = "Hello World!"
    return mime_message


class TestSend:
    async def test(
        self,
        smtp_backend: SMTPEmailBackend,
        smtp_server: SMTPDummyServer,
        message: MIMEText,
    ):
        async with smtp_backend:
            await smtp_backend.send(message)

        assert "Hello World!" in smtp_server.messages[0]
