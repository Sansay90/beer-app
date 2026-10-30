"""Оборудование пивовара — всё, на чём и чем он варит, бродит, меряет и разливает (виды и их параметры — kinds.py).

Варочные системы — кастрюля или котёл, автоматическая пивоварня, Easy Brew Connect — с объёмом партии,
эффективностью, испарением и объёмом котла: на них варят («Сварить»), одна из них — основная (её цифры — в новые
рецепты и расчёт воды). Первая добавленная система — основная; основную удалили — основной становится самая ранняя
из оставшихся. Основная у пользователя одна: правки основной идут под замком на строку пользователя, база держит
то же частичным уникальным индексом. У прочего — свои параметры (props). У всего — заметки. Пивоварню, которую
завёл агент, оборудованием делает attach_device; пока она привязана, это оборудование не удалить. Сайт управляет
одной пивоварней пользователя — последней заведённой (controlled_device): связь и калибровка — у её оборудования.
"""
from sqlalchemy import func
from sqlmodel import select

from ..db import session
from ..errors import Conflict, Invalid, NotFound
from ..models import Device, Equipment, User, parse_id
from .kinds import KINDS, SYSTEM_DEFAULTS, SYSTEMS, check_params, is_system

MANUAL, EASYBREW = "manual", "easybrew"
MAX = 100
NAME_MAX = 60
NOTES_MAX = 2000


def check_name(name):
    name = (name or "").strip()
    if not name:
        raise Invalid("назовите оборудование")
    if len(name) > NAME_MAX:
        raise Invalid(f"название длиннее {NAME_MAX} знаков — сократите")
    return name


def check_notes(notes):
    notes = (notes or "").strip()
    if len(notes) > NOTES_MAX:
        raise Invalid(f"заметки длиннее {NOTES_MAX} знаков — сократите")
    return notes or None


def view(e, controlled=None):
    """Оборудование для API; controlled — id пивоварни, которой управляет сайт. Вида уже нет в каталоге —
    видно как «Другое» (вид остаётся прежним: его сохранённое не теряется)."""
    k = KINDS.get(e.kind) or KINDS["other"]
    return {"id": str(e.id), "name": e.name, "kind": e.kind, "category": k["category"], "system": k["system"],
            "connected": e.device_id is not None, "controlled": e.device_id is not None and e.device_id == controlled,
            "main": e.main, "volume": e.volume, "efficiency": e.efficiency, "evaporation": e.evaporation,
            "kettle": e.kettle, "props": e.props or {}, "notes": e.notes}


def own(s, user_id, equipment_id):
    """Оборудование пользователя по id; чужое или нет такого — NotFound."""
    e = s.get(Equipment, eid) if (eid := parse_id(equipment_id)) else None
    if e is None or e.user_id != user_id:
        raise NotFound("оборудование не найдено")
    return e


def main_of(s, user_id):
    """Основная варочная система пользователя или None."""
    return s.exec(select(Equipment).where(Equipment.user_id == user_id, Equipment.main)).first()


def controlled_device(s, user_id):
    """Пивоварня, которой управляет сайт: пока у пользователя она одна — последняя заведённая; или None."""
    return s.exec(select(Device.id).where(Device.user_id == user_id).order_by(Device.created_at.desc())).first()


def lock_user(s, user_id):
    """Замок на строку пользователя до конца транзакции: правки основной системы — по одной."""
    s.exec(select(User.id).where(User.id == user_id).with_for_update()).first()


def attach_device(s, device):
    """Пивоварня, которую агент завёл впервые, — оборудованием пивовара: заранее добавленное «Easy Brew» без
    пивоварни получает её, иначе заводится новое (со средними цифрами); основным — если основного ещё нет.
    В сессии s, без commit."""
    lock_user(s, device.user_id)
    e = s.exec(select(Equipment).where(Equipment.user_id == device.user_id, Equipment.kind == EASYBREW,
                                       Equipment.device_id.is_(None)).order_by(Equipment.created_at)).first()
    if e is None:
        e = Equipment(user_id=device.user_id, name=device.name or "Easy Brew", kind=EASYBREW, **SYSTEM_DEFAULTS,
                      main=main_of(s, device.user_id) is None)
    e.device_id = device.id
    s.add(e)


def apply(e, name, columns, props, notes):
    """Записать в e название, параметры по его виду (kinds.check_params) и заметки."""
    e.name, e.notes = check_name(name), check_notes(notes)
    cols, e.props = check_params(e.kind, columns, props)
    for key, value in cols.items():
        setattr(e, key, value)


class EquipmentStore:
    """Оборудование пользователя user. NotFound — чужое или нет такого."""

    def __init__(self, user):
        self.user = user

    def list(self):
        """Основное первым, остальное — по порядку добавления."""
        with session() as s:
            rows = s.exec(select(Equipment).where(Equipment.user_id == self.user.id)
                          .order_by(Equipment.main.desc(), Equipment.created_at)).all()
            controlled = controlled_device(s, self.user.id)
        return [view(e, controlled) for e in rows]

    def create(self, name, kind, volume=None, efficiency=None, evaporation=None, kettle=None, props=None, notes=None):
        with session() as s:
            lock_user(s, self.user.id)
            mine = s.exec(select(func.count()).select_from(Equipment).where(Equipment.user_id == self.user.id)).one()
            if mine >= MAX:
                raise Conflict(f"оборудования уже {MAX} — удалите ненужное")
            e = Equipment(user_id=self.user.id, kind=kind, name="")
            apply(e, name, {"volume": volume, "efficiency": efficiency, "evaporation": evaporation, "kettle": kettle},
                  props, notes)
            e.main = is_system(kind) and main_of(s, self.user.id) is None
            s.add(e)
            s.commit()
            return self._view(s, e)

    def update(self, equipment_id, name, volume=None, efficiency=None, evaporation=None, kettle=None, props=None,
               notes=None):
        """Вид оборудования не меняется."""
        with session() as s:
            e = self._row(s, equipment_id)
            apply(e, name, {"volume": volume, "efficiency": efficiency, "evaporation": evaporation, "kettle": kettle},
                  props, notes)
            s.add(e)
            s.commit()
            return self._view(s, e)

    def make_main(self, equipment_id):
        with session() as s:
            lock_user(s, self.user.id)
            e = self._row(s, equipment_id)
            if not is_system(e.kind):
                raise Invalid("основной бывает только варочная система: на ней варят")
            if (old := main_of(s, self.user.id)) is not None and old.id != e.id:
                old.main = False
                s.add(old)
                s.flush()                                   # снять старую до новой: основная в базе одна
            e.main = True
            s.add(e)
            s.commit()
            return self._view(s, e)

    def delete(self, equipment_id):
        with session() as s:
            lock_user(s, self.user.id)
            e = self._row(s, equipment_id)
            if e.device_id is not None:
                raise Conflict("пивоварня подключена к сайту — сначала отвяжите её")
            s.delete(e)
            if e.main:
                s.flush()
                rest = s.exec(select(Equipment).where(Equipment.user_id == self.user.id, Equipment.id != e.id,
                                                      Equipment.kind.in_(SYSTEMS))
                              .order_by(Equipment.created_at)).first()
                if rest is not None:
                    rest.main = True
                    s.add(rest)
            s.commit()

    def _row(self, s, equipment_id):
        return own(s, self.user.id, equipment_id)

    def _view(self, s, e):
        return view(e, controlled_device(s, self.user.id))
