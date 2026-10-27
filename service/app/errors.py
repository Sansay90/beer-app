"""Ошибки предметной области. Модули данных бросают их с текстом для человека, а HTTP-статус и ответ
{"detail": текст} им подбирает обработчик (install) — роутеры не переводят исключения вручную."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status = 500

    def __init__(self, detail, status=None):
        super().__init__(detail)
        self.detail = detail
        if status is not None:
            self.status = status


class Invalid(AppError):
    """Неверные данные."""
    status = 400


class Forbidden(AppError):
    """Видно, но этого нельзя."""
    status = 403


class NotFound(AppError):
    """Нет такого — или не видно тому, кто спрашивает: чужое личное не выдаём даже существованием."""
    status = 404


class Conflict(AppError):
    """Нельзя в текущем состоянии."""
    status = 409


def install(app: FastAPI):
    @app.exception_handler(AppError)
    async def app_error(request: Request, e: AppError):
        return JSONResponse({"detail": e.detail}, status_code=e.status)
