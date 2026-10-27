"""Схемы API рецептов. Рецепт описывает пиво (по мотивам BeerJSON); программа пивоварни — затирание
и кипячение — и напоминания на кипячении выводятся из него (program.py).
Плотность — SG (1.048), цвет — EBC, объём — л, солод — кг, хмель — г."""
from typing import Literal

from pydantic import BaseModel, Field

from ..auth.schemas import Author

AdditionKind = Literal["hop", "spice", "fining", "water", "adjunct", "sugar", "equipment"]
Unit = Literal["g", "kg", "ml", "pcs", "pkg"]


class Addition(BaseModel):
    """Что заложить в кипячение: хмель, специи, осветлитель, соли, добавка, сахар или оборудование (чиллер)."""
    minutes: int = Field(description="минут до конца кипячения")
    kind: AdditionKind = "hop"
    name: str | None = None
    amount: float | None = Field(None, description="у оборудования не бывает")
    unit: Unit = "g"
    whirlpool: int | None = Field(None, description="вирпул: закладывают в конце кипячения и выдерживают "
                                                    "столько минут; None — не вирпул")


class AdditionSlot(BaseModel):
    """Таймер пивоварни и всё, что закладывают по нему: на одну минуту — один писк."""
    minutes: int = Field(description="минут до конца кипячения")
    items: list[Addition] = Field(description="пусто — рецепт загружен не из приложения")
    label: str


class StyleRef(BaseModel):
    code: str | None = Field(None, description="стиль BJCP 2021, напр. 5B; None — свой стиль")
    name: str


class Batch(BaseModel):
    volume: float | None = Field(None, description="л сусла после кипячения — к нему считаются OG, IBU и цвет")
    efficiency: float | None = Field(None, description="эффективность, %: экстракт в сусле после кипячения "
                                                         "/ экстракт засыпи")


class Targets(BaseModel):
    """Показатели по ингредиентам: сервис считает их сам при сохранении (calc.py) — присланные не сохраняются."""
    og: float | None = Field(None, description="начальная плотность, SG")
    fg: float | None = Field(None, description="конечная плотность, SG")
    ibu: float | None = None
    ebc: float | None = None
    abv: float | None = Field(None, description="крепость, % об. — с сахаром, добавленным на брожении")


class Fermentable(BaseModel):
    name: str = ""
    kind: Literal["grain", "adjunct", "sugar", "extract"] = "grain"
    amount: float | None = Field(None, description="кг")
    ebc: float | None = None
    use: Literal["mash", "boil", "fermentation"] = "mash"
    minutes: int | None = Field(None, description="кипячение — за сколько минут до конца")


class Hop(BaseModel):
    name: str = ""
    alpha: float | None = Field(None, description="альфа-кислоты, %")
    amount: float | None = Field(None, description="г")
    use: Literal["mash", "first_wort", "boil", "whirlpool", "dry_hop"] = "boil"
    minutes: int | None = Field(None, description="кипячение — за сколько минут до конца; вирпул — сколько стоит")
    day: int | None = Field(None, description="сухое охмеление — день брожения")


class Misc(BaseModel):
    name: str = ""
    kind: Literal["spice", "fining", "adjunct", "equipment"] = "adjunct"
    amount: float | None = Field(None, description="у оборудования не бывает")
    unit: Unit = "g"
    use: Literal["mash", "boil", "whirlpool", "fermentation", "packaging"] = "boil"
    minutes: int | None = Field(None, description="кипячение — за сколько минут до конца")


class WaterProfile(BaseModel):
    """Ионы, мг/л."""
    ca: float = 0
    mg: float = 0
    na: float = 0
    cl: float = 0
    so4: float = 0
    hco3: float = 0


WaterAgent = Literal["cacl2", "cacl2_anhydrous", "gypsum", "nacl", "nahco3", "caco3", "epsom",
                     "lactic80", "lactic88", "other"]


class WaterAddition(BaseModel):
    """Соль (г) или кислота (мл) в заторную или промывочную воду."""
    agent: WaterAgent
    name: str = Field("", description="для agent = other")
    amount: float | None = None
    target: Literal["mash", "sparge"] = "mash"


class Water(BaseModel):
    """Заторная вода = гидромодуль × засыпь; промывочная — остальное до объёма перед кипячением
    с поправкой на дробину (считает интерфейс: испарение — у оборудования, а не в рецепте)."""
    ratio: float | None = Field(None, description="гидромодуль — заторная вода к засыпи, л/кг")
    source: WaterProfile = Field(default_factory=WaterProfile, description="исходная вода; нули — осмос")
    additions: list[WaterAddition] = []


class Yeast(BaseModel):
    name: str = ""
    form: Literal["dry", "liquid"] = "dry"
    amount: float | None = None
    unit: Unit = "pkg"
    attenuation: float | None = Field(None, description="степень сбраживания, %")


class MashStep(BaseModel):
    name: str | None = None
    temp: float
    minutes: int
    watts: int


class Boil(BaseModel):
    minutes: int
    watts: int


class FermentationStep(BaseModel):
    name: str | None = None
    temp: float
    days: float


class Recipe(BaseModel):
    name: str
    style: StyleRef | None = None
    batch: Batch = Field(default_factory=Batch)
    targets: Targets = Field(default_factory=Targets)
    fermentables: list[Fermentable] = []
    hops: list[Hop] = []
    miscs: list[Misc] = []
    yeasts: list[Yeast] = []
    water: Water = Field(default_factory=Water)
    mash: list[MashStep] = []
    boil: Boil | None = None
    fermentation: list[FermentationStep] = []
    notes: str = ""


Visibility = Literal["private", "public"]


class RecipeSummary(BaseModel):
    id: str
    name: str
    style: StyleRef | None = None
    targets: Targets
    volume: float | None = Field(None, description="л сусла после кипячения")
    steps: int = Field(description="шагов программы пивоварни")
    minutes: int = Field(description="длительность программы без учёта нагрева")
    brews: int = Field(description="сколько раз варили")
    lastBrewedAt: float | None = None
    updatedAt: float
    about: str = Field("", description="первый абзац описания (notes) — для карточки")
    photos: list[str] = Field([], description="id фото пива, старые первыми — миниатюры на карточке")
    author: Author = Field(description="автор: ник и аватар, без почты")
    mine: bool = Field(False, description="рецепт того, кто спрашивает")
    visibility: Visibility = "private"
    publishedAt: float | None = None
    favorite: bool = Field(False, description="в избранном у того, кто спрашивает")
    likes: int = Field(0, description="«нравится»")
    dislikes: int = Field(0, description="«не нравится»")
    comments: int = Field(0, description="комментариев, без удалённых")
    brewsTotal: int = Field(0, description="сколько раз варили все пивовары (через пивоварню)")


class RecipeMeta(BaseModel):
    """Что о рецепте знать интерфейсу: автор, видимость и что можно тому, кто спрашивает (access.py)."""
    author: Author
    mine: bool
    visibility: Visibility
    publishedAt: float | None = None
    favorite: bool = Field(False, description="в избранном у того, кто спрашивает")
    likes: int = 0
    dislikes: int = 0
    vote: int = Field(0, description="голос того, кто спрашивает: 1, −1 или 0")
    comments: int = 0
    brewsTotal: int = Field(0, description="сколько раз варили все пивовары")
    canEdit: bool = Field(description="править, удалять, публиковать, добавлять фото — рецепт свой")
    canModerate: bool = Field(description="снять с публикации, удалить, убрать фото — администратор, рецепт чужой")


class RecipeDetail(Recipe):
    meta: RecipeMeta


class VoteIn(BaseModel):
    value: int = Field(description="1 — нравится, −1 — не нравится, 0 — снять голос")


class Votes(BaseModel):
    likes: int
    dislikes: int
    vote: int


class CommentIn(BaseModel):
    text: str = Field(max_length=4000)
    parentId: str | None = Field(None, description="ответ на комментарий; ответ на ответ встаёт в ту же ветку")


class CommentEdit(BaseModel):
    text: str = Field(max_length=4000)


class CommentOut(BaseModel):
    """Комментарий; удалённый с ответами — пустой (deleted), без автора."""
    id: str
    parentId: str | None = None
    author: Author | None = None
    text: str
    createdAt: float
    edited: bool
    deleted: bool
    likes: int
    dislikes: int
    vote: int = Field(description="голос того, кто спрашивает")
    canEdit: bool
    canDelete: bool


class VisibilityIn(BaseModel):
    visibility: Visibility


class Photo(BaseModel):
    """Фото пива по рецепту; сама картинка — GET /api/photos/{id}."""
    id: str
    credit: str | None = Field(None, description="автор и лицензия, если фото чужое")
    createdAt: float


class SavedRecipe(BaseModel):
    id: str
