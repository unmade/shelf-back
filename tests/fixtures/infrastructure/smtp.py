import pytest
from aiosmtpd.controller import Controller

from app.config import MailSMTPConfig
from app.infrastructure.mail.smtp import SMTPEmailBackend


@pytest.fixture(scope="module")
def smtp_mail_config() -> MailSMTPConfig:
    return MailSMTPConfig(smtp_hostname="localhost", smtp_port=8026)


class DummyHandler:
    __slots__ = ["messages"]

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def handle_DATA(self, server, session, envelope):
        self.messages.append(envelope.content.decode())
        return '250 Message accepted for delivery'


class SMTPDummyServer:
    __slots__ = ["controller"]

    def __init__(self, hostname: str, port: int):
        self.controller = Controller(
            DummyHandler(),
            hostname=hostname,
            port=port,
        )

    @property
    def messages(self) -> list[str]:
        handler: DummyHandler = self.controller.handler
        return handler.messages

    def start(self) -> None:
        self.controller.start()

    def stop(self) -> None:
        self.controller.stop()


@pytest.fixture(scope="module")
def smtp_server(smtp_mail_config: MailSMTPConfig):
    server = SMTPDummyServer(smtp_mail_config.smtp_hostname, smtp_mail_config.smtp_port)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def smtp_backend(smtp_mail_config: MailSMTPConfig) -> SMTPEmailBackend:
    return SMTPEmailBackend(smtp_mail_config)
