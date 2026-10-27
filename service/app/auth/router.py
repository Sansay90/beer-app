"""Вход по почте и паролю: регистрация, вход и выход, подтверждение почты и новый пароль по ссылке из письма."""
from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ..deps import LimitsDep, MailerDep, SettingsDep
from ..mail import reset_letter, verify_letter
from ..recipes.photos import TYPES
from ..schemas import Ok
from . import profile, sessions, users
from .dependencies import SESSION_COOKIE, CurrentUser
from .schemas import Credentials, EmailIn, Me, NameIn, RegisterIn, ResetIn, TokenIn

router = APIRouter(prefix="/auth", tags=["вход"])


def client_ip(request):
    return f"ip:{request.client.host if request.client else '?'}"


def too_many(wait):
    raise HTTPException(429, f"слишком много попыток — попробуйте через {max(1, round(wait / 60))} мин")


def throttle(*pairs):
    """Засчитать попытку по каждой паре (лимит, ключ); где лимит исчерпан — 429."""
    if wait := max(limiter.wait(key) for limiter, key in pairs):
        too_many(wait)
    for limiter, key in pairs:
        limiter.add(key)


def site_url(request, settings):
    """Адрес сайта для ссылок в письмах. Без APP_URL — только адрес на этом же ПК: иначе подставной заголовок
    отправил бы ссылку сброса пароля на чужой сайт."""
    if settings.site_url:
        return settings.site_url
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    if settings.trusted_origin.fullmatch(origin):
        return origin
    raise HTTPException(500, "на сервере не задан APP_URL — адрес сайта для ссылок в письмах")


def start_session(request, response, user):
    token = sessions.start(user.id, request.headers.get("user-agent"))
    response.set_cookie(SESSION_COOKIE, token, max_age=sessions.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https", path="/")


def send_verify(base, mailer, user):
    link = f"{base}/verify?token={sessions.issue_link_token(user.id, 'verify')}"
    mailer.send(user.email, *verify_letter(user.email, link))


@router.post("/register", response_model=Me, summary="Зарегистрироваться и войти",
             description="Письмо со ссылкой подтверждения почты уходит сразу; входить можно и до подтверждения.")
def register(body: RegisterIn, request: Request, response: Response, settings: SettingsDep, mailer: MailerDep,
             limits: LimitsDep):
    throttle((limits.signups_by_ip, client_ip(request)))
    base = site_url(request, settings)                  # до записи: без адреса для ссылки регистрировать нельзя
    user = users.register(body.email, body.password, body.name, settings.admins)
    start_session(request, response, user)
    send_verify(base, mailer, user)
    return users.me(user)


@router.post("/login", response_model=Me, summary="Войти")
def login(body: Credentials, request: Request, response: Response, limits: LimitsDep):
    ip, email = client_ip(request), f"email:{body.email.strip().lower()}"
    if wait := max(limits.failed_by_ip.wait(ip), limits.failed_by_email.wait(email)):
        too_many(wait)
    user = users.authenticate(body.email, body.password)
    if user is None:                                     # считаются только неудачные попытки
        limits.failed_by_ip.add(ip)
        limits.failed_by_email.add(email)
        raise HTTPException(401, "неверная почта или пароль")
    start_session(request, response, user)
    return users.me(user)


@router.post("/logout", response_model=Ok, summary="Выйти")
def logout(request: Request, response: Response):
    sessions.end(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Ok()


@router.get("/me", response_model=Me, summary="Кто вошёл")
def get_me(user: CurrentUser):
    return users.me(user)


@router.patch("/me", response_model=Me, summary="Сменить ник",
              description="Ник уникален без учёта регистра и «е/ё»; занят или не по правилам — 400.")
def set_name(body: NameIn, user: CurrentUser):
    return users.me(profile.set_name(user.id, body.name))


@router.put("/me/avatar", response_model=Me, summary="Поставить аватар",
            description="Тело — сама картинка, JPEG, PNG или WebP, до 5 МБ; сервис обрежет её до квадрата 256 px.",
            openapi_extra={"requestBody": {"required": True, "content": {
                t: {"schema": {"type": "string", "format": "binary"}} for t in TYPES}}})
async def set_avatar(request: Request, user: CurrentUser):
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > profile.AVATAR_MAX_BYTES:
            raise HTTPException(413, "картинка больше 5 МБ")
    avatar = await run_in_threadpool(profile.prepare_avatar, bytes(data))
    return users.me(await run_in_threadpool(profile.set_avatar, user.id, avatar))


@router.delete("/me/avatar", response_model=Me, summary="Убрать аватар")
def remove_avatar(user: CurrentUser):
    return users.me(profile.set_avatar(user.id, None))


@router.post("/verify", response_model=Me, summary="Подтвердить почту по ссылке из письма")
def verify(body: TokenIn):
    return users.me(sessions.verify_email(body.token))


@router.post("/verify/resend", response_model=Ok, summary="Прислать письмо подтверждения ещё раз")
def resend_verify(user: CurrentUser, request: Request, settings: SettingsDep, mailer: MailerDep, limits: LimitsDep):
    if user.email_verified_at is None:
        throttle((limits.letters_by_email, f"email:{user.email}"))
        send_verify(site_url(request, settings), mailer, user)
    return Ok()


@router.post("/forgot", response_model=Ok, summary="Прислать ссылку для нового пароля",
             description="Отвечает одинаково, есть такая почта или нет.")
def forgot(body: EmailIn, request: Request, settings: SettingsDep, mailer: MailerDep, limits: LimitsDep):
    email = body.email.strip().lower()
    throttle((limits.letters_by_ip, client_ip(request)), (limits.letters_by_email, f"email:{email}"))
    base = site_url(request, settings)
    user = users.by_email(email)
    if user is not None:
        mailer.send(user.email, *reset_letter(f"{base}/reset?token={sessions.issue_link_token(user.id, 'reset')}"))
    return Ok()


@router.post("/reset", response_model=Me, summary="Задать новый пароль по ссылке и войти",
             description="Прежние входы на всех устройствах закрываются.")
def reset(body: ResetIn, request: Request, response: Response):
    user = sessions.reset_password(body.token, body.password)
    start_session(request, response, user)
    return users.me(user)
