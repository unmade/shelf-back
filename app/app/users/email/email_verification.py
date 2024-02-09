from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from app import template
from app.toolkit import taskgroups

if TYPE_CHECKING:
    from app.app.users.domain import User

__all__ = ["EmailVerificationMessage"]


class EmailVerificationMessage:
    __slots__ = ("recipient", "code")

    templates = [
        template.engine.get_template("mail/users/email_verification/email.html"),
        template.engine.get_template("mail/users/email_verification/email.txt"),
    ]

    def __init__(self, recipient: User, code: str):
        self.recipient = recipient
        self.code = code

    def get_context(self):
        return {
           "display_name": self.recipient.display_name,
           "email": self.recipient.email,
           "code": self.code,
        }

    async def build(self) -> MIMEMultipart:
        html, txt = await taskgroups.gather(*(
            template.render_async(**self.get_context())
            for template in self.templates
        ))

        message = MIMEMultipart("alternative")
        message["From"] = "no-reply@getshelf.cloud"
        message["To"] = self.recipient.email
        message["Subject"] = "Email Verification"

        message.attach(MIMEText(txt, "plain", "utf-8"))
        message.attach(MIMEText(html, "html", "utf-8"))

        return message
