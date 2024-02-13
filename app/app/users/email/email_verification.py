from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app import template
from app.toolkit import taskgroups

__all__ = ["EmailVerificationMessage"]


class EmailVerificationMessage:
    __slots__ = ("code", "display_name", "email")

    templates = [
        template.engine.get_template("mail/users/email_verification/email.html"),
        template.engine.get_template("mail/users/email_verification/email.txt"),
    ]

    def __init__(self, display_name: str, email: str, code: str):
        self.display_name = display_name
        self.email = email
        self.code = code

    def get_context(self):
        return {
           "display_name": self.display_name,
           "email": self.email,
           "code": self.code,
        }

    async def build(self) -> MIMEMultipart:
        html, txt = await taskgroups.gather(*(
            template.render_async(**self.get_context())
            for template in self.templates
        ))

        message = MIMEMultipart("alternative")
        message["From"] = "no-reply@getshelf.cloud"
        message["To"] = self.email
        message["Subject"] = "Email Verification"

        message.attach(MIMEText(txt, "plain", "utf-8"))
        message.attach(MIMEText(html, "html", "utf-8"))

        return message
