"""Разведка Easy Brew по локальной сети: какие точки данных (DP) отдаёт пивоварня.

Из папки brewapp/server:
    .venv\\Scripts\\python tools\\probe.py dump     снимок всех DP с именами из dpmap.json
    .venv\\Scripts\\python tools\\probe.py watch    журнал изменений DP в реальном времени (Ctrl+C — стоп)

Нужен devices.json от `python -m tinytuya wizard` в brewapp/server (см. README.md).
"""
import argparse
import base64
import binascii
import csv
import json
import os
import sys
import time
from datetime import datetime

import tinytuya

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # brewapp/server
DEVICES_FILE = os.path.join(APP_DIR, "devices.json")
DPMAP_FILE = os.path.join(APP_DIR, "dpmap.json")
LOG_DIR = os.path.join(APP_DIR, "logs")
HEARTBEAT_S = 10

sys.stdout.reconfigure(errors="replace")   # вывод в файл из cp1251-консоли не должен падать


# ── Устройство ────────────────────────────────────────────────────────────────
def load_device(name_filter):
    if not os.path.exists(DEVICES_FILE):
        sys.exit(f"Нет {DEVICES_FILE} — сначала получить ключи через wizard (README.md).")
    with open(DEVICES_FILE, encoding="utf-8") as f:
        devices = [d for d in json.load(f) if d.get("key")]
    found = devices
    if name_filter:
        found = [d for d in devices if name_filter.lower() in d.get("name", "").lower()]
    if len(found) == 1:
        return found[0]
    print(f"Нужно ровно одно устройство, подошло: {len(found)}. Все устройства аккаунта:")
    for d in devices:
        print(f"  {d.get('name')!r:32} {d.get('product_name', '')}")
    sys.exit("Уточнить через --dev <часть имени>.")


def load_mapping(dev):
    # стандартная карта в devices.json знает только 6 DP; полная — из облачной модели устройства
    if os.path.exists(DPMAP_FILE):
        with open(DPMAP_FILE, encoding="utf-8") as f:
            return json.load(f)
    return dev.get("mapping") or {}


def connect(dev, ip, version):
    ip = ip or dev.get("ip") or dev.get("last_ip")
    version = version or dev.get("version")
    if not (ip and version):
        # адрес и версию протокола пивоварня сообщает сама в UDP-широковещании
        return tinytuya.Device(dev["id"], address="Auto", local_key=dev["key"])
    return tinytuya.Device(dev["id"], address=ip, local_key=dev["key"], version=float(version))


# ── Форматирование ────────────────────────────────────────────────────────────
def fmt(value, meta):
    kind = meta.get("type", "").lower()
    spec = meta.get("values")
    if kind == "integer" and isinstance(value, int) and isinstance(spec, dict):
        scale = spec.get("scale") or 0
        unit = spec.get("unit", "")
        if scale or unit:
            return f"{value}  (= {value / 10 ** scale:g} {unit})".replace(" )", ")")
    if kind == "raw" and isinstance(value, str):
        try:
            return f"{value}  [hex: {base64.b64decode(value, validate=True).hex(' ')}]"
        except (binascii.Error, ValueError):
            pass
    return repr(value)


def describe(meta):
    spec = meta.get("values")
    if not isinstance(spec, dict):
        return ""
    if "range" in spec:
        return "варианты: " + ", ".join(map(str, spec["range"]))
    if "min" in spec:
        return (f"диапазон {spec['min']}…{spec['max']}, шаг {spec.get('step', 1)}, "
                f"scale {spec.get('scale', 0)} {spec.get('unit', '')}").rstrip()
    return ""


def dp_order(dp):
    return int(dp) if dp.isdigit() else 10 ** 6


# ── Режимы ────────────────────────────────────────────────────────────────────
def cmd_dump(d, mapping):
    st = d.status()
    if not st or "Error" in st:
        sys.exit(f"Ошибка связи: {st}")
    dps = st.get("dps", {})
    for dp in sorted(set(dps) | set(mapping), key=dp_order):
        meta = mapping.get(dp, {})
        value = fmt(dps[dp], meta) if dp in dps else "— (в status не пришёл)"
        print(f"DP {dp:>4}  {meta.get('code', '?'):<22} {meta.get('type', ''):<8} {value}")
        notes = " · ".join(filter(None, [meta.get("ru"), describe(meta)]))
        if notes:
            print(" " * 10 + notes)

    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"dump_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"dps": dps, "mapping": mapping}, f, ensure_ascii=False, indent=2)
    print(f"\nСнимок сохранён: {path}")


def cmd_watch(d, mapping):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"watch_{datetime.now():%Y%m%d_%H%M%S}.csv")
    d.set_socketPersistent(True)
    last = {}
    last_hb = time.monotonic()
    print(f"Слушаю пивоварню, журнал: {path}")
    print("Меняйте режимы в штатном приложении или кнопками на пивоварне — "
          "каждое изменение DP появится здесь. Ctrl+C — стоп.\n")

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["время", "dp", "код", "значение"])
        data = d.status()
        try:
            while True:
                if data and "Error" in data:
                    print(f"{datetime.now():%H:%M:%S}  связь: {data['Error']} — переподключаюсь")
                    time.sleep(2)
                    data = d.status()
                    continue
                if data and "dps" in data:
                    now = datetime.now()
                    for dp, value in sorted(data["dps"].items(), key=lambda kv: dp_order(kv[0])):
                        if dp in last and last[dp] == value:
                            continue
                        last[dp] = value
                        meta = mapping.get(dp, {})
                        print(f"{now:%H:%M:%S}  DP {dp:>4}  {meta.get('code', '?'):<22} {fmt(value, meta)}"
                              f"   {meta.get('ru', '')}".rstrip())
                        w.writerow([now.isoformat(timespec="seconds"), dp, meta.get("code", ""), value])
                    f.flush()
                if time.monotonic() - last_hb > HEARTBEAT_S:
                    d.heartbeat()
                    last_hb = time.monotonic()
                data = d.receive()
        except KeyboardInterrupt:
            print(f"\nСтоп. Журнал: {path}")


def main():
    p = argparse.ArgumentParser(description="Разведка точек данных Easy Brew по локальной сети")
    p.add_argument("mode", choices=["dump", "watch"])
    p.add_argument("--dev", help="часть имени устройства, если в аккаунте Tuya их несколько")
    p.add_argument("--ip", help="IP пивоварни, если автопоиск не находит")
    p.add_argument("--version", type=float, help="версия протокола Tuya (3.3 / 3.4 / 3.5)")
    args = p.parse_args()

    dev = load_device(args.dev)
    print(f"Устройство: {dev.get('name')}  ({dev.get('product_name', '')})")
    try:
        d = connect(dev, args.ip, args.version)
    except RuntimeError:
        sys.exit("Пивоварня не найдена в сети. Она включена, ПК в той же Wi-Fi-сети? "
                 "Можно указать --ip и --version вручную (видны в devices.json после wizard).")
    print(f"Адрес {d.address}, протокол {d.version}\n")

    mapping = load_mapping(dev)
    if not mapping:
        print("Внимание: нет ни dpmap.json, ни карты DP в devices.json — имена будут '?'.\n")
    (cmd_dump if args.mode == "dump" else cmd_watch)(d, mapping)


if __name__ == "__main__":
    main()
