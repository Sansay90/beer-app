"""Рецепты и фото пива. Гость видит опубликованные, пользователь — ещё и свои (права — access.py)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from ..auth.dependencies import CurrentUser, Viewer
from ..brewery.control import UserBrewery
from ..schemas import Ok
from . import photos as photo
from .calc import targets
from .program import build_program
from .schemas import Photo, Recipe, RecipeDetail, RecipeSummary, SavedRecipe, VisibilityIn
from .store import RecipeStore

router = APIRouter(tags=["рецепты"])


def viewer_recipes(viewer: Viewer) -> RecipeStore:
    """Рецепты глазами того, кто спрашивает: гостю — опубликованные, пользователю — ещё и свои."""
    return RecipeStore(viewer)


def user_recipes(user: CurrentUser) -> RecipeStore:
    return RecipeStore(user)


ViewerRecipes = Annotated[RecipeStore, Depends(viewer_recipes)]
UserRecipes = Annotated[RecipeStore, Depends(user_recipes)]


@router.get("/recipes", response_model=list[RecipeSummary],
            summary="Опубликованные рецепты и свои, недавно изменённые первыми",
            description="mine — только свои, favorites — только избранные.")
def list_recipes(recipes: ViewerRecipes, mine: bool = False, favorites: bool = False):
    if (mine or favorites) and recipes.viewer is None:
        raise HTTPException(401, "войдите")
    return recipes.list(mine, favorites)


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
