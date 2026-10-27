"""Профиль: ник и аватар — то, что о пользователе видят все. Почту видят только он сам и администратор.
Ника может не быть (при регистрации он необязателен) — тогда интерфейс пишет «Неизвестный пивовар».

Ник уникален без учёта регистра и разницы «е/ё» (name_key — для сравнения): по нему страница пивовара
/brewers/{ник}. Буквы — русские или латинские, не вперемешку: «Ivаn» с русской «а» не выдать за «Ivan».
Аватар — квадрат 256 px JPEG в базе; нет своего — интерфейс рисует бокал (по id пользователя).
"""
import io
import re

from PIL import Image, ImageOps
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..access import PUBLIC
from ..db import session
from ..errors import Invalid, NotFound
from ..models import Recipe, User, parse_id, unix
from ..recipes.photos import Unsupported, photo_type

NICK_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё_-]{2,23}")
RESERVED = {"admin", "administrator", "root", "support", "moderator", "hoplab", "brewapp", "me", "new", "settings",
            "админ", "администратор", "модератор", "поддержка", "пивоварня"}
AVATAR_SIDE = 256
AVATAR_MAX_BYTES = 5 * 1024 * 1024


def nick_key(nick):
    return nick.casefold().replace("ё", "е")


def check_nick(nick):
    """Ник без пробелов по краям; Invalid — не подходит по правилам."""
    nick = (nick or "").strip()
    if not NICK_RE.fullmatch(nick):
        raise Invalid("ник — от 3 до 24 знаков: буквы, цифры, «_» и «-»; начинается с буквы или цифры")
    if re.search(r"[A-Za-z]", nick) and re.search(r"[А-Яа-яЁё]", nick):
        raise Invalid("в нике — русские или латинские буквы, не вперемешку")
    if nick_key(nick) in RESERVED:
        raise Invalid("этот ник занят — придумайте другой")
    return nick


def nick_taken(s, nick, except_id=None):
    q = select(User.id).where(User.name_key == nick_key(nick))
    if except_id is not None:
        q = q.where(User.id != except_id)
    return s.exec(q).first() is not None


TAKEN = "этот ник занят — придумайте другой"


def set_name(user_id, nick):
    """Сменить ник → пользователь. Invalid — не подходит или занят."""
    nick = check_nick(nick)
    with session() as s:
        user = s.get(User, user_id)
        if nick_taken(s, nick, user.id):
            raise Invalid(TAKEN)
        user.name, user.name_key = nick, nick_key(nick)
        s.add(user)
        try:
            s.commit()
        except IntegrityError:
            raise Invalid(TAKEN) from None
        s.refresh(user)
        return user


def prepare_avatar(data: bytes) -> bytes:
    """Аватар из присланной картинки: квадрат по центру, 256 px, JPEG. Unsupported — не картинка."""
    if photo_type(data) is None:
        raise Unsupported()
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (AVATAR_SIDE, AVATAR_SIDE))
            out = io.BytesIO()
            im.save(out, "JPEG", quality=85, optimize=True)
            return out.getvalue()
    except (OSError, Image.DecompressionBombError) as e:
        raise Unsupported() from e


def set_avatar(user_id, avatar: bytes | None):
    """Поставить (готовый JPEG) или убрать аватар → пользователь. Версия растёт — старый адрес не из кеша."""
    with session() as s:
        user = s.get(User, user_id)
        user.avatar, user.avatar_version = avatar, user.avatar_version + 1
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def avatar_url(user_id, version, has_avatar):
    return f"/api/avatars/{user_id}?v={version}" if has_avatar else None


def author(user_id, name, version, has_avatar):
    """Автор для интерфейса: id (по нему — бокал вместо аватара), ник, адрес аватара."""
    return {"id": str(user_id), "name": name, "avatar": avatar_url(user_id, version, has_avatar)}


def avatar_image(user_id):
    with session() as s:
        user = s.get(User, uid) if (uid := parse_id(user_id)) else None
        if user is None or user.avatar is None:
            raise NotFound("аватара нет")
        return user.avatar


def by_nick(s, nick):
    """Зарегистрированный пользователь по нику или None."""
    return s.exec(select(User).where(User.name_key == nick_key((nick or "").strip()),
                                     User.email.is_not(None))).first()


def brewer(nick):
    """Страница пивовара: ник, аватар, с какого времени на сайте, сколько опубликованных рецептов."""
    with session() as s:
        user = by_nick(s, nick)
        if user is None:
            raise NotFound("пивовар не найден")
        recipes = s.exec(select(func.count()).select_from(Recipe)
                         .where(Recipe.user_id == user.id, Recipe.visibility == PUBLIC)).one()
        return {**author(user.id, user.name, user.avatar_version, user.avatar is not None),
                "joinedAt": unix(user.created_at), "recipes": recipes}
