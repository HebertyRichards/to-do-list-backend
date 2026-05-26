from fastapi_mail import ConnectionConfig, FastMail, MessageSchema

from app.config.settings import get_settings


def get_mail_config() -> ConnectionConfig:
    s = get_settings()
    return ConnectionConfig(
        MAIL_USERNAME=s.email_user,
        MAIL_PASSWORD=s.email_pass,
        MAIL_FROM=s.email_user,
        MAIL_PORT=465,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_STARTTLS=False,
        MAIL_SSL_TLS=True,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


async def send_email(subject: str, recipients: list[str], body: str) -> None:
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html",
    )
    fm = FastMail(get_mail_config())
    await fm.send_message(message)
