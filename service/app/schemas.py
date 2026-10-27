"""Общие схемы API. Остальные — у своих разделов (auth/, recipes/, brewery/, push/). Из схем FastAPI строит
OpenAPI, а из него генерируются TS-типы интерфейса (web: npm run api:types) — один источник формы данных."""
from pydantic import BaseModel


class Ok(BaseModel):
    ok: bool = True
