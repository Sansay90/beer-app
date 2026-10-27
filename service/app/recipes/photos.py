"""Фото пива: проверка картинки и превью для списков."""
import io

from PIL import Image, ImageOps

from ..errors import AppError

MAX_BYTES = 10 * 1024 * 1024
PER_RECIPE = 12
TYPES = ("image/jpeg", "image/png", "image/webp")
THUMB_SIDE = 480


class Unsupported(AppError):
    status = 415

    def __init__(self):
        super().__init__("нужна картинка JPEG, PNG или WebP")


def prepare(data: bytes):
    """(тип, превью) для новой фотографии. Unsupported — не картинка JPEG, PNG или WebP либо не открывается."""
    kind = photo_type(data)
    if kind is None:
        raise Unsupported()
    return kind, thumbnail(data)


def photo_type(data: bytes):
    """Тип картинки по сигнатуре файла — заголовку Content-Type не верим; не картинка — None."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def thumbnail(data: bytes) -> bytes:
    """Превью для списков — JPEG до 480 px; заодно проверка, что картинка открывается (иначе Unsupported)."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((THUMB_SIDE, THUMB_SIDE))
            out = io.BytesIO()
            im.convert("RGB").save(out, "JPEG", quality=80, optimize=True)
            return out.getvalue()
    except (OSError, Image.DecompressionBombError) as e:
        raise Unsupported() from e
