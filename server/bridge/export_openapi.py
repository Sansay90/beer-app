"""Выгрузить OpenAPI-схему посредника — из неё генерируются TS-типы интерфейса.

    .venv\\Scripts\\python -m bridge.export_openapi [путь]     (или в web: npm run api:types)

По умолчанию пишет в ../web/openapi.json.
"""
import json
import os
import sys

from .server import APP_DIR, app

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(APP_DIR), "web", "openapi.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(app.openapi(), f, ensure_ascii=False, indent=2)
print(path)
