"""Фото пива: тип по сигнатуре, превью; загрузка и права — через API."""
import io
import urllib.request

import pytest
from PIL import Image

from app.recipes import photos


def png(size=(1200, 800)):
    out = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(out, "PNG")
    return out.getvalue()


def test_type_by_signature():
    assert photos.photo_type(png()) == "image/png"
    assert photos.photo_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert photos.photo_type(b"RIFF\0\0\0\0WEBPVP8 ") == "image/webp"
    assert photos.photo_type(b"<svg/>") is None


def test_prepare_makes_thumbnail():
    kind, thumb = photos.prepare(png())
    assert kind == "image/png"
    with Image.open(io.BytesIO(thumb)) as im:
        assert im.format == "JPEG" and max(im.size) == photos.THUMB_SIDE


def test_prepare_rejects():
    with pytest.raises(photos.Unsupported):
        photos.prepare(b"not an image")
    with pytest.raises(photos.Unsupported):
        photos.prepare(b"\x89PNG\r\n\x1a\n broken")


def upload(client, rid, data):
    req = urllib.request.Request(f"{client.base}/api/recipes/{rid}/photos", data=data, method="POST",
                                 headers={"Content-Type": "image/png"})
    try:
        with client.opener.open(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_upload_and_rights(service, brewer, recipe):
    rid = brewer.ok("POST", "/recipes", recipe)["id"]
    assert upload(brewer, rid, b"not an image") == 415
    assert upload(brewer, rid, png()) == 200
    [photo] = brewer.ok("GET", f"/recipes/{rid}/photos")
    guest = service.client()
    assert guest.get(f"/recipes/{rid}/photos")[0] == 404             # рецепт личный — и фото не видно
    other = service.client()
    other.signup("other@test.local")
    assert upload(other, rid, png()) == 404
    assert other.delete(f"/photos/{photo['id']}")[0] == 404
    brewer.ok("DELETE", f"/photos/{photo['id']}")
    assert brewer.ok("GET", f"/recipes/{rid}/photos") == []
