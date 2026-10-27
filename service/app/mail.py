"""Письма пользователям: подтверждение почты и сброс пароля.

SMTP — SMTP_HOST, SMTP_PORT (465 — SSL, иначе STARTTLS), SMTP_USER, SMTP_PASSWORD, SMTP_FROM (по умолчанию SMTP_USER).
Без SMTP_HOST письма не уходят: их текст со ссылкой пишется в журнал сервиса — для разработки на своём ПК. Перед тем
как открыть регистрацию посторонним, SMTP нужно настроить. Отправка — в своём потоке: запрос не ждёт почтовый сервер.
"""
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

log = logging.getLogger("brewapp.mail")
TIMEOUT_S = 20


class Mailer:
    def __init__(self, settings):
        self.host, self.port = settings.smtp_host, settings.smtp_port
        self.user, self.password = settings.smtp_user, settings.smtp_password
        self.sender = settings.smtp_from or settings.smtp_user

    def send(self, to, subject, text):
        if not self.host:
            log.warning("SMTP не настроен — письмо не отправлено. Кому: %s · %s\n%s", to, subject, text)
            return
        threading.Thread(target=self._send, args=(to, subject, text), name="mail", daemon=True).start()

    def _send(self, to, subject, text):
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        ctx = ssl.create_default_context()
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, context=ctx, timeout=TIMEOUT_S) as smtp:
                    self._deliver(smtp, msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=TIMEOUT_S) as smtp:
                    smtp.starttls(context=ctx)
                    self._deliver(smtp, msg)
        except Exception as e:
            log.error("письмо на %s не отправлено: %s", to, e)

    def _deliver(self, smtp, msg):
        if self.user:
            smtp.login(self.user, self.password)
        smtp.send_message(msg)


def verify_letter(email, link):
    return ("Подтвердите почту — Пивоварня",
            f"Здравствуйте!\n\nЧтобы подтвердить адрес {email} в Пивоварне, откройте ссылку:\n{link}\n\n"
            "Ссылка действует 2 дня. Если вы не регистрировались, просто удалите это письмо.\n")


def reset_letter(link):
    return ("Новый пароль — Пивоварня",
            f"Здравствуйте!\n\nЧтобы задать новый пароль, откройте ссылку:\n{link}\n\n"
            "Ссылка действует час и сработает один раз. Если вы не просили сменить пароль, просто удалите это письмо — "
            "пароль останется прежним.\n")
