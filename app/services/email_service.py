import logging

from app.config.email import send_email

logger = logging.getLogger(__name__)


class EmailService:
    async def send_password_reset_code(self, to: str, code: str) -> None:
        subject = "Redefinição de senha — To-Do List"
        body = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Redefinição de senha</h2>
          <p>Use o código abaixo para redefinir sua senha. Ele expira em <strong>10 minutos</strong>.</p>
          <div style="font-size:2.5rem;font-weight:bold;letter-spacing:0.5rem;text-align:center;
                      padding:1.5rem;background:#f4f4f5;border-radius:8px;margin:1.5rem 0">
            {code}
          </div>
          <p style="color:#71717a;font-size:0.85rem">Se você não solicitou a redefinição, ignore este email.</p>
        </div>
        """
        try:
            await send_email(subject=subject, recipients=[to], body=body)
            logger.info("Email de reset enviado para %s", to)
        except Exception:
            logger.exception("Falha ao enviar email de reset para %s", to)
            raise

    async def send_email_verification_code(self, to: str, code: str) -> None:
        subject = "Confirme seu email — To-Do List"
        body = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Confirme seu email</h2>
          <p>Bem-vindo! Use o código abaixo para confirmar seu email e ativar sua conta. Ele expira em <strong>1 hora</strong>.</p>
          <div style="font-size:2.5rem;font-weight:bold;letter-spacing:0.5rem;text-align:center;
                      padding:1.5rem;background:#f4f4f5;border-radius:8px;margin:1.5rem 0">
            {code}
          </div>
          <p style="color:#71717a;font-size:0.85rem">Se você não criou esta conta, ignore este email.</p>
        </div>
        """
        try:
            await send_email(subject=subject, recipients=[to], body=body)
            logger.info("Email de verificação enviado para %s", to)
        except Exception:
            logger.exception("Falha ao enviar email de verificação para %s", to)
            raise
