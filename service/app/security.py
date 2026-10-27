"""Изменяющие запросы — только со своего сайта: cookie входа браузер приложит и к форме, отправленной с чужой
страницы (CSRF). Свой сайт — тот же адрес, что у сервиса, или APP_URL; без APP_URL — ещё dev-сервер на этом ПК."""
from starlette.requests import Request
from starlette.responses import JSONResponse

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
DRAIN_MAX = 1024 * 1024                  # тело отклонённого запроса дочитать (до 1 МБ), иначе клиент получит обрыв


def trusted(origin, request, pattern):
    return origin == f"{request.url.scheme}://{request.headers.get('host', '')}" or bool(pattern.fullmatch(origin))


async def drain(receive):
    read = 0
    while read <= DRAIN_MAX:
        message = await receive()
        read += len(message.get("body", b""))
        if message["type"] != "http.request" or not message.get("more_body"):
            return


class OwnSiteOnly:
    """ASGI-прослойка: поток SSE и WebSocket проходят сквозь неё нетронутыми."""

    def __init__(self, app, pattern):
        self.app = app
        self.pattern = pattern

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            request = Request(scope)
            origin = request.headers.get("origin")
            if origin and not trusted(origin, request, self.pattern):
                await drain(receive)
                await JSONResponse({"detail": "запрос с чужого сайта"}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)
