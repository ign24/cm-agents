"""Base class para agentes."""

import os
from abc import ABC, abstractmethod
from pathlib import Path

from dotenv import load_dotenv


class BaseAgent(ABC):
    """Clase base para todos los agentes."""

    def __init__(self):
        load_dotenv()
        self._validate_env()

    @abstractmethod
    def _validate_env(self) -> None:
        """Valida que las variables de entorno necesarias estén configuradas."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del agente."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción del agente."""
        pass

    def _get_env(self, key: str) -> str:
        """Obtiene una variable de entorno o lanza error."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Variable de entorno {key} no configurada")
        return value


def load_image_as_base64(image_path: Path) -> str:
    """Carga una imagen y la convierte a base64."""
    import base64

    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_image_media_type(image_path: Path) -> str:
    """Determina el media type de una imagen."""
    suffix = image_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(suffix, "image/jpeg")


def parse_data_url(data_url: str) -> tuple[str, str]:
    """
    Parsea un data URL (p. ej. del frontend) en (media_type, base64_data).

    Formato: data:image/png;base64,XXXX o data:image/jpeg;base64,XXXX
    Retorna media_type (p. ej. image/png) y el payload base64 sin prefijo.
    """
    if not data_url.startswith("data:"):
        return "image/jpeg", data_url  # asumir base64 crudo
    try:
        header, payload = data_url.split(",", 1)
        # header: "data:image/png;base64" o "data:image/jpeg;base64"
        parts = header[len("data:") :].split(";")
        media = parts[0].strip().lower()
        if not media.startswith("image/"):
            media = "image/jpeg"
        return media, payload.strip()
    except Exception:
        return "image/jpeg", data_url
