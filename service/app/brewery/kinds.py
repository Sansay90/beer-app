"""Каталог оборудования пивовара: группы, виды и их параметры — всё, на чём и чем варят, бродят, меряют и разливают.

Варочные системы (system) — то, на чём варят: «Сварить» пересчитывает рецепт партии под их объём, эффективность
и испарение, основное подставляется в новые рецепты; их параметры — столбцы equipment (volume, efficiency,
evaporation, kettle). У прочих видов параметры — свои, в equipment.props, и пока только описывают оборудование.
Интерфейс строит формы и подписи по этому же каталогу (GET /api/equipment/kinds); иконки видов — у интерфейса.
Убрать или переименовать вид — только с миграцией данных: до неё такое оборудование видно как «Другое»
и не правится (equipment.view).
Поле: key, label, type (number | select | bool), для числа — unit, min, max, step, digits (знаков после запятой),
prefix (перед значением в кратком описании: «котёл 40 л»), default — у нового; для выбора — options; для «да/нет» —
short (в кратком описании, если да); help — подсказка под полем.
"""
from ..errors import Invalid
from ..recipes.program import ru_num


def number(key, label, unit, lo, hi, step=1, digits=0, help=None, prefix=None, default=None):
    return {"key": key, "label": label, "type": "number", "unit": unit, "min": lo, "max": hi, "step": step,
            "digits": digits, "help": help, "prefix": prefix, "default": default}


def select(key, label, options, help=None):
    return {"key": key, "label": label, "type": "select", "options": [{"value": v, "label": t} for v, t in options],
            "help": help}


def flag(key, label, short, help=None):
    return {"key": key, "label": label, "type": "bool", "short": short, "help": help}


SYSTEM_FIELDS = [
    number("volume", "Объём партии", "л", 0.5, 2000, digits=1, help="После кипячения"),
    number("efficiency", "Эффективность", "%", 1, 100, help="Для новых рецептов", default=75.0),
    number("evaporation", "Испарение", "л/ч", 0, 20, step=0.1, digits=1, help="За час, без крышки", default=3.0),
    number("kettle", "Объём котла", "л", 1, 5000, digits=1, prefix="котёл",
           help="До краёв — проверить, влезет ли варка"),
]
SYSTEM_DEFAULTS = {f["key"]: f["default"] for f in SYSTEM_FIELDS if f["default"] is not None}
VOLUME = number("volume", "Объём", "л", 0.1, 5000, digits=1)
ATC = flag("atc", "Термокомпенсация (ATC)", "ATC")


def offset(unit, lo, hi, step, digits, help):
    """Погрешность прибора: сколько он показывает сверх эталона; плюс — завышает."""
    return number("offset", "Погрешность", unit, lo, hi, step=step, digits=digits, prefix="погрешность", help=help)


def kind(id, label, hint, fields=(), system=False, ranges=()):
    """ranges — пары полей «от» и «до»: «от» не больше «до»."""
    return {"id": id, "label": label, "hint": hint, "system": system,
            "fields": list(SYSTEM_FIELDS if system else fields), "ranges": list(ranges)}


CATEGORIES = [
    {"id": "brew", "label": "Варка", "kinds": [
        kind("manual", "Кастрюля или котёл", "На плите, газе или электрокотле", system=True),
        kind("allinone", "Автоматическая пивоварня", "Brewzilla, Grainfather, Braumeister и другие — без подключения "
                                                    "к сайту", system=True),
        kind("easybrew", "Easy Brew Connect", "Пивоварня, которой управляют с сайта: программа, закладки, график "
                                              "варки", system=True),
        kind("mash_tun", "Заторный кулер", "Изотермический бак для затирания", [VOLUME]),
        kind("hlt", "Котёл для промывочной воды", "Нагрев воды для промывки", [VOLUME]),
        kind("burner", "Горелка или плита", "Газовая, индукционная, электрическая",
             [number("power", "Мощность", "кВт", 0.1, 50, step=0.5, digits=1)]),
        kind("hop_spider", "Хмелевой фильтр", "Hop Spider, мешок для хмеля"),
    ]},
    {"id": "mill", "label": "Помол", "kinds": [
        kind("mill", "Мельница", "Дробилка для солода", [
            number("gap_min", "Зазор от", "мм", 0.1, 3, step=0.05, digits=2, prefix="зазор от",
                   help="Пределы регулировки валков"),
            number("gap_max", "Зазор до", "мм", 0.1, 3, step=0.05, digits=2, prefix="до"),
            select("rollers", "Валков", [("2", "2 валка"), ("3", "3 валка")]),
        ], ranges=[("gap_min", "gap_max")]),
    ]},
    {"id": "chill", "label": "Охлаждение сусла", "kinds": [
        kind("chiller", "Чиллер", "Охлаждение сусла после кипячения", [
            select("type", "Тип", [("immersion", "погружной"), ("counterflow", "противоточный"),
                                   ("plate", "пластинчатый")]),
        ]),
        kind("pump", "Насос", "Перекачка сусла и воды", [flag("hot", "Для горячего сусла", "для горячего")]),
    ]},
    {"id": "ferment", "label": "Брожение", "kinds": [
        kind("fermenter", "Ферментер", "Ведро, бутыль, ЦКТ", [
            VOLUME,
            number("pressure", "Давление", "бар", 0, 5, step=0.1, digits=1, prefix="до",
                   help="Сколько держит; 0 — без давления"),
            select("cooling", "Охлаждение", [("none", "без охлаждения"), ("jacket", "рубашка"), ("coil", "змеевик")]),
        ]),
        kind("chamber", "Камера брожения", "Холодильник или морозильник под брожение",
             [number("min_temp", "Холоднее всего", "°C", -10, 25, digits=1, prefix="от")]),
        kind("glycol", "Гликолевый охладитель", "Охлаждение рубашки или змеевика ферментера",
             [number("min_temp", "Холоднее всего", "°C", -10, 25, digits=1, prefix="от")]),
        kind("controller", "Контроллер температуры", "STC, Inkbird и другие", [
            select("channels", "Управляет", [("cool", "охлаждением"), ("heat", "нагревом"),
                                             ("both", "охлаждением и нагревом")]),
        ]),
        kind("heater", "Нагреватель", "Пояс, коврик, тэн в камере", [number("power", "Мощность", "Вт", 1, 5000)]),
        kind("sensor", "Датчик плотности", "Tilt, iSpindel, RAPT Pill"),
    ]},
    {"id": "measure", "label": "Измерения", "kinds": [
        kind("hydrometer", "Ареометр", "Плотность сусла и пива", [
            offset("°P", -5, 5, 0.1, 1, "Что показывает на чистой воде; плюс — завышает"),
            number("calibration_temp", "Калиброван при", "°C", 10, 30, step=0.5, digits=1, prefix="при",
                   help="Написано на шкале: обычно 20 °C"),
        ]),
        kind("refractometer", "Рефрактометр", "Плотность по капле сусла", [
            offset("°Bx", -5, 5, 0.1, 1, "Что показывает на чистой воде; плюс — завышает"), ATC]),
        kind("ph_meter", "pH-метр", "Кислотность затора и сусла", [
            offset("pH", -2, 2, 0.01, 2, "Против буферного раствора; плюс — завышает"), ATC]),
        kind("thermometer", "Термометр", "Щуп, пирометр, стрелочный", [
            offset("°C", -10, 10, 0.1, 1, "Против эталонного термометра; плюс — завышает")]),
        kind("scale", "Весы", "Солод, хмель, соли", [
            number("max", "Предел", "кг", 0.01, 500, step=0.5, digits=2, prefix="до"),
            number("precision", "Точность", "г", 0.001, 100, step=0.01, digits=3),
        ]),
    ]},
    {"id": "yeast", "label": "Дрожжи", "kinds": [
        kind("stir_plate", "Магнитная мешалка", "Для стартера"),
        kind("flask", "Колба", "Стартер дрожжей", [number("volume", "Объём", "л", 0.1, 20, step=0.5, digits=1)]),
    ]},
    {"id": "package", "label": "Розлив и газ", "kinds": [
        kind("keg", "Кег", "Cornelius, Sanke и другие", [VOLUME]),
        kind("co2", "Баллон CO₂", "С редуктором", [number("volume", "Объём", "л", 0.5, 50, step=0.5, digits=1)]),
        kind("tap", "Система розлива", "Кран, пистолет, «фонтан»"),
        kind("kegerator", "Кегератор", "Холодильник под кеги",
             [number("taps", "Кранов", "", 1, 20, prefix="кранов:")]),
        kind("filter", "Фильтр", "Осветление перед розливом",
             [number("micron", "Тонкость", "мкм", 0.1, 100, step=0.5, digits=1)]),
        kind("bottles", "Бутылки и укупорка", "Бутылки, крышки, укупорщик"),
    ]},
    {"id": "other", "label": "Другое", "kinds": [
        kind("other", "Другое", "Всё, чего нет в списке"),
    ]},
]
KINDS = {k["id"]: {**k, "category": c["id"]} for c in CATEGORIES for k in c["kinds"]}
KIND_IDS = tuple(KINDS)
SYSTEMS = tuple(k for k, v in KINDS.items() if v["system"])


def is_system(kind_id):
    return KINDS.get(kind_id, {}).get("system", False)


COLUMNS = tuple(f["key"] for f in SYSTEM_FIELDS)    # параметры варочной системы — столбцы equipment


def check_values(label, fields, values):
    """Значения по полям fields: только их ключи, числа — в пределах и не точнее digits, выбор — из списка,
    «да/нет» — bool; пустые выкидываются. label — вид, для текста ошибки. Invalid — что не так."""
    fields = {f["key"]: f for f in fields}
    out = {}
    for key, value in (values or {}).items():
        if value is None or value == "":
            continue
        f = fields.get(key)
        if f is None:
            raise Invalid(f"у вида «{label}» нет параметра «{key}»")
        if f["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise Invalid(f"«{f['label']}» — число")
            if not f["min"] <= value <= f["max"]:
                raise Invalid(f"«{f['label']}» — от {ru_num(f['min'])} до {ru_num(f['max'])} {f['unit']}".rstrip())
            if abs(round(value, f["digits"]) - value) > 1e-9:
                raise Invalid(f"«{f['label']}» — " + ("целое число" if not f["digits"]
                                                       else f"не больше {f['digits']} знаков после запятой"))
            out[key] = float(value)
        elif f["type"] == "select":
            if value not in {o["value"] for o in f["options"]}:
                raise Invalid(f"«{f['label']}» — выберите из списка")
            out[key] = value
        else:
            if not isinstance(value, bool):
                raise Invalid(f"«{f['label']}» — да или нет")
            out[key] = value
    return out


def check_params(kind_id, columns, props):
    """(столбцы, props) оборудования вида kind_id: у варочной системы — её столбцы (не указанные эффективность
    и испарение — средние), props пусты; у прочего — props, столбцы пусты. Прислали чужое для вида — Invalid."""
    k = KINDS.get(kind_id)
    if k is None:
        raise Invalid("неизвестный вид оборудования")
    given = {key: v for key, v in (columns or {}).items() if v is not None}
    if k["system"]:
        if any(v not in (None, "") for v in (props or {}).values()):
            raise Invalid("у варочной системы параметры — объём партии, эффективность, испарение и котёл")
        cols = {**dict.fromkeys(COLUMNS), **SYSTEM_DEFAULTS, **check_values(k["label"], k["fields"], given)}
        return cols, {}
    if given:
        raise Invalid(f"у вида «{k['label']}» нет объёма партии, эффективности, испарения и котла — "
                      "его параметры в props")
    out = check_values(k["label"], k["fields"], props)
    fields = {f["key"]: f for f in k["fields"]}
    for lo, hi in k["ranges"]:
        if lo in out and hi in out and out[lo] > out[hi]:
            raise Invalid(f"«{fields[lo]['label']}» больше, чем «{fields[hi]['label']}»")
    return dict.fromkeys(COLUMNS), out
