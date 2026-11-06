"""Picture of the car in the color chosen in the settings (files in the integration's images folder)."""
from __future__ import annotations

import mimetypes
import os

from homeassistant.components.image import ImageEntity
from homeassistant.util import dt as dt_util

from .const import CONF_COLOR, IMAGE_EXTENSIONS
from .entity import Ex5Entity

IMAGES = os.path.join(os.path.dirname(__file__), "images")


def list_colors() -> list[str]:
    """Color names = image file names without extension (e.g. "azul-celeste.png" -> "azul-celeste")."""
    if not os.path.isdir(IMAGES):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(IMAGES)
                  if f.lower().endswith(IMAGE_EXTENSIONS) and not f.startswith("."))


def color_file(color: str | None) -> str | None:
    if not color:
        return None
    for ext in IMAGE_EXTENSIONS:
        path = os.path.join(IMAGES, color + ext)
        if os.path.isfile(path):
            return path
    return None


async def async_setup_entry(hass, entry, add) -> None:
    t = entry.runtime_data
    path = await hass.async_add_executor_job(color_file, t.options.get(CONF_COLOR))
    if path:
        add([CarImage(hass, t, path)])


class CarImage(Ex5Entity, ImageEntity):
    def __init__(self, hass, tracker, path: str) -> None:
        Ex5Entity.__init__(self, tracker, "car", "image")
        ImageEntity.__init__(self, hass)
        self._path = path
        self._attr_content_type = mimetypes.guess_type(path)[0] or "image/png"
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        def read() -> bytes:
            with open(self._path, "rb") as f:
                return f.read()

        return await self.hass.async_add_executor_job(read)
