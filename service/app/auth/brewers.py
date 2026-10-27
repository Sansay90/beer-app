"""Пивовары глазами всех, и гостей: страница пивовара и аватар. Почты здесь нет (profile.py)."""
from fastapi import APIRouter, Response

from . import profile
from .schemas import Brewer

router = APIRouter(tags=["пивовары"])


@router.get("/brewers/{nick}", response_model=Brewer, summary="Пивовар по нику",
            description="Его опубликованные рецепты — GET /api/recipes?author={nick}.")
def get_brewer(nick: str):
    return profile.brewer(nick)


@router.get("/avatars/{uid}", response_class=Response, summary="Аватар — сама картинка",
            description="Адрес с ?v= берётся из ответа сервиса: у нового аватара новая версия, поэтому кеш вечный.",
            responses={200: {"content": {"image/jpeg": {}}}})
def get_avatar(uid: str):
    return Response(profile.avatar_image(uid), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "X-Content-Type-Options": "nosniff"})
