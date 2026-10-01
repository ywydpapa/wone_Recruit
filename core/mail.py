import os
import smtplib
import ssl
from email.message import EmailMessage

from core.logger import log


# SMTP_HOST 미설정 시 실제 발송 없이 로그만 기록함 (개발용)
def send_mail(to, subject, body):
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("메일 미발송(SMTP 미설정) to=%s subject=%s\n%s", to, subject, body)
        return True

    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = os.getenv("MAIL_FROM") or user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    ctx = ssl.create_default_context()
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
        else:
            smtp = smtplib.SMTP(host, port, timeout=10)
            smtp.starttls(context=ctx)
        with smtp:
            if user:
                smtp.login(user, os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception as e:
        log.warning("메일 발송 실패 to=%s: %s", to, e)
        return False
