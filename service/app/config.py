"""Настройки сервиса — из переменных окружения или service/.env (образец — .env.example).

Пустая переменная окружения считается незаданной: тогда берётся значение из .env или по умолчанию.
"""
import os
import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/service
# без APP_URL сервис стоит у пивовара дома: интерфейсу из dev-сервера на этом же ПК — можно
LOCAL_ORIGIN = re.compile(r"https?://(localhost|127\.0\.0\.1)(:\d+)?")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(SERVICE_DIR, ".env"), env_file_encoding="utf-8",
                                      env_ignore_empty=True, extra="ignore")

    database_url: str = Field("", repr=False)
    # адрес сайта: ссылки в письмах и проверка источника запросов; пусто — сервис на своём ПК
    app_url: str = ""
    # почты администраторов через запятую; пусто — администратор первый зарегистрировавшийся (auth/users.py)
    admin_emails: str = ""

    # письма (mail.py); без SMTP_HOST текст письма со ссылкой пишется в журнал
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = Field("", repr=False)
    smtp_from: str = ""

    # Web Push (push/): закрытый ключ сервера — python -m app vapid; пусто — уведомления выключены
    vapid_private_key: str = Field("", repr=False)
    vapid_subject: str = "mailto:brewapp@example.com"

    service_host: str = "127.0.0.1"
    service_port: int = 8000
    # за reverse proxy: чьим заголовкам X-Forwarded-* верить (схема https для cookie, адрес клиента для лимитов)
    forwarded_allow_ips: str = "127.0.0.1"

    # свойства, а не cached_property: копия настроек (model_copy) не должна унести чужие значения
    @property
    def site_url(self):
        return self.app_url.rstrip("/")

    @property
    def trusted_origin(self):
        """Чьи страницы могут слать изменяющие запросы с cookie входа: свой сайт, без APP_URL — этот ПК."""
        return re.compile(re.escape(self.site_url)) if self.site_url else LOCAL_ORIGIN

    @property
    def admins(self):
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}
