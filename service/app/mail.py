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

from . import db

log = logging.getLogger("brewapp.mail")
TIMEOUT_S = 20


def send(to, subject, text):
    host = db.env("SMTP_HOST")
    if not host:
        log.warning("SMTP не настроен — письмо не отправлено. Кому: %s · %s\n%s", to, subject, text)
        return
    threading.Thread(target=_send, args=(host, to, subject, text), name="mail", daemon=True).start()


def _send(host, to, subject, text):
    port = int(db.env("SMTP_PORT", "465"))
    user, password = db.env("SMTP_USER"), db.env("SMTP_PASSWORD")
    msg = EmailMessage()
    msg["From"] = db.env("SMTP_FROM") or user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    ctx = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=TIMEOUT_S) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=TIMEOUT_S) as smtp:
                smtp.starttls(context=ctx)
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except Exception as e:
        log.error("письмо на %s не отправлено: %s", to, e)


def verify_letter(email, link):
    return ("Подтвердите почту — Пивоварня",
            f"Здравствуйте!\n\nЧтобы подтвердить адрес {email} в Пивоварне, откройте ссылку:\n{link}\n\n"
            "Ссылка действует 2 дня. Если вы не регистрировались, просто удалите это письмо.\n")


def reset_letter(link):
    return ("Новый пароль — Пивоварня",
            f"Здравствуйте!\n\nЧтобы задать новый пароль, откройте ссылку:\n{link}\n\n"
            "Ссылка действует час и сработает один раз. Если вы не просили сменить пароль, просто удалите это письмо — "
            "пароль останется прежним.\n")
