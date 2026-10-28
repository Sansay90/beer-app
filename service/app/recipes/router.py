"""Рецепты, обсуждение и фото пива. Гость видит опубликованные, пользователь — ещё и свои (права — access.py)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from ..auth.dependencies import CurrentUser, Viewer
from ..brewery.control import UserBrewery
from ..deps import LimitsDep, PusherDep
from ..notifications.feed import Notices
from ..schemas import Ok
from . import photos as photo
from .calc import targets
from .discussion import Discussion
from .program import build_program
from .schemas import (
    CommentEdit,
    CommentIn,
    CommentOut,
    Photo,
    Recipe,
    RecipeDetail,
    RecipeSummary,
    SavedRecipe,
    VisibilityIn,
    VoteIn,
    Votes,
)
from .store import RecipeStore

router = APIRouter(tags=["рецепты"])


def viewer_recipes(viewer: Viewer) -> RecipeStore:
    """Рецепты глазами того, кто спрашивает: гостю — опубликованные, пользователю — ещё и свои."""
    return RecipeStore(viewer)


def user_recipes(user: CurrentUser) -> RecipeStore:
    return RecipeStore(user)


ViewerRecipes = Annotated[RecipeStore, Depends(viewer_recipes)]
UserRecipes = Annotated[RecipeStore, Depends(user_recipes)]


def viewer_discussion(viewer: Viewer, pusher: PusherDep) -> Discussion:
    return Discussion(viewer, Notices(pusher))


def user_discussion(user: CurrentUser, pusher: PusherDep) -> Discussion:
    return Discussion(user, Notices(pusher))


ViewerDiscussion = Annotated[Discussion, Depends(viewer_discussion)]
UserDiscussion = Annotated[Discussion, Depends(user_discussion)]


@router.get("/recipes", response_model=list[RecipeSummary],
            summary="Опубликованные рецепты и свои, недавно изменённые первыми",
            description="mine — только свои, favorites — только избранные, author — рецепты пивовара по нику.")
def list_recipes(recipes: ViewerRecipes, mine: bool = False, favorites: bool = False,
                 author: str | None = Query(None, max_length=40)):
    if (mine or favorites) and recipes.viewer is None:
        raise HTTPException(401, "войдите")
    return recipes.list(mine, favorites, author)


@router.get("/recipes/{rid}", response_model=RecipeDetail,
            summary="Рецепт: свой или опубликованный; meta — автор и что можно тому, кто спрашивает")
def get_recipe(rid: str, recipes: ViewerRecipes):
    return recipes.detail(rid)


async def save(recipes, brewery, rid, body):
    recipe = body.model_dump(exclude_none=True)
    # показатели — посчитанные сервисом по ингредиентам, присланные не сохраняются
    recipe["targets"] = {k: v for k, v in targets(recipe).items() if v is not None}
    await run_in_threadpool(brewery.check, recipe)          # до записи: пивоварня должна принять программу
    saved_id = await run_in_threadpool(recipes.save, rid, recipe)
    await brewery.recipe_changed(saved_id, recipe)
    return {"id": saved_id}


@router.post("/recipes", response_model=SavedRecipe, summary="Создать рецепт")
async def create_recipe(body: Recipe, recipes: UserRecipes, brewery: UserBrewery):
    return await save(recipes, brewery, None, body)


@router.put("/recipes/{rid}", response_model=SavedRecipe, summary="Сохранить рецепт")
async def update_recipe(rid: str, body: Recipe, recipes: UserRecipes, brewery: UserBrewery):
    return await save(recipes, brewery, rid, body)


@router.delete("/recipes/{rid}", response_model=Ok)
async def delete_recipe(rid: str, recipes: UserRecipes, brewery: UserBrewery):
    await run_in_threadpool(recipes.delete, rid)
    await brewery.recipe_deleted(rid)
    return Ok()


@router.put("/recipes/{rid}/visibility", response_model=Ok, summary="Опубликовать или снять с публикации",
            description="Автор — в обе стороны, публиковать — с подтверждённой почтой; "
                        "администратор — снять чужой рецепт.")
def set_visibility(rid: str, body: VisibilityIn, recipes: UserRecipes):
    recipes.set_visibility(rid, body.visibility)
    return Ok()


@router.put("/recipes/{rid}/favorite", response_model=Ok, summary="В избранное",
            description="Любой видимый рецепт, свой тоже; уже в избранном — ничего не меняется.")
def add_favorite(rid: str, recipes: UserRecipes):
    recipes.set_favorite(rid, True)
    return Ok()


@router.delete("/recipes/{rid}/favorite", response_model=Ok, summary="Из избранного")
def remove_favorite(rid: str, recipes: UserRecipes):
    recipes.set_favorite(rid, False)
    return Ok()


@router.post("/recipes/{rid}/upload", response_model=Ok, summary="Загрузить рецепт в пивоварню",
             description="Свой или опубликованный: варить можно и по чужому рецепту.")
async def upload(rid: str, recipes: UserRecipes, brewery: UserBrewery):
    recipe = await run_in_threadpool(recipes.get, rid)
    await run_in_threadpool(brewery.check, recipe)
    return await brewery.run("upload", program=build_program(rid, recipe))


# ── обсуждение и голоса ───────────────────────────────────────────────────────
@router.get("/recipes/{rid}/comments", response_model=list[CommentOut], summary="Комментарии к рецепту",
            description="Старые первыми; ответ — с parentId (уровень один).")
def list_comments(rid: str, discussion: ViewerDiscussion):
    return discussion.comments(rid)


@router.post("/recipes/{rid}/comments", response_model=CommentOut, summary="Написать комментарий",
             description="Вошедшему; не чаще 5 в минуту и 60 в час.")
def add_comment(rid: str, body: CommentIn, discussion: UserDiscussion, limits: LimitsDep):
    key = f"user:{discussion.uid}"
    if wait := max(limits.comments_burst.wait(key), limits.comments_by_user.wait(key)):
        raise HTTPException(429, f"слишком часто — попробуйте через {max(1, round(wait / 60))} мин")
    comment = discussion.add(rid, body.text, body.parentId)
    limits.comments_burst.add(key)
    limits.comments_by_user.add(key)
    return comment


@router.patch("/comments/{cid}", response_model=CommentOut, summary="Изменить свой комментарий")
def edit_comment(cid: str, body: CommentEdit, discussion: UserDiscussion):
    return discussion.edit(cid, body.text)


@router.delete("/comments/{cid}", response_model=Ok, summary="Удалить комментарий",
               description="Свой — автору, любой — администратору; с ответами остаётся «комментарий удалён».")
def delete_comment(cid: str, discussion: UserDiscussion):
    discussion.remove(cid)
    return Ok()


@router.put("/recipes/{rid}/vote", response_model=Votes, summary="Голос за рецепт",
            description="1 — нравится, −1 — не нравится, 0 — снять; за свой рецепт — нельзя.")
def vote_recipe(rid: str, body: VoteIn, discussion: UserDiscussion):
    return discussion.vote_recipe(rid, body.value)


@router.put("/comments/{cid}/vote", response_model=Votes, summary="Голос за комментарий")
def vote_comment(cid: str, body: VoteIn, discussion: UserDiscussion):
    return discussion.vote_comment(cid, body.value)


# ── фото пива ─────────────────────────────────────────────────────────────────
@router.get("/recipes/{rid}/photos", response_model=list[Photo], summary="Фото пива по рецепту")
def list_photos(rid: str, recipes: ViewerRecipes):
    return recipes.photos(rid)


@router.post("/recipes/{rid}/photos", response_model=Photo, summary="Добавить фото пива",
             description="Тело — сама картинка, JPEG, PNG или WebP, до 10 МБ (интерфейс заранее уменьшает её). "
                         "credit — автор и лицензия, если фото чужое.",
             openapi_extra={"requestBody": {"required": True, "content": {
                 t: {"schema": {"type": "string", "format": "binary"}} for t in photo.TYPES}}})
async def add_photo(rid: str, request: Request, recipes: UserRecipes,
                    credit: str | None = Query(None, max_length=300)):
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > photo.MAX_BYTES:
            raise HTTPException(413, "фото больше 10 МБ")
    kind, thumb = await run_in_threadpool(photo.prepare, bytes(data))
    return await run_in_threadpool(recipes.add_photo, rid, kind, bytes(data), thumb, credit, photo.PER_RECIPE)


@router.get("/photos/{pid}", response_class=Response, summary="Фото — сама картинка",
            responses={200: {"content": {t: {} for t in photo.TYPES}}})
def get_photo(pid: str, recipes: ViewerRecipes,
              thumb: bool = Query(False, description="превью до 480 px вместо полного снимка")):
    kind, data = recipes.photo(pid, thumb)
    # фото не меняется — у нового снимка новый id
    return Response(data, media_type=kind, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                                    "X-Content-Type-Options": "nosniff"})


@router.delete("/photos/{pid}", response_model=Ok, summary="Удалить фото")
def delete_photo(pid: str, recipes: UserRecipes):
    recipes.delete_photo(pid)
    return Ok()
