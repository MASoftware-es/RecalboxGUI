"""Acceso centralizado a los recursos gráficos de la aplicación."""

from pathlib import Path


ASSETS_DIR = Path(__file__).resolve().parent
APP_ICON_PATH = ASSETS_DIR / "appicon.png"
DIALOG_SOUND_PATH = ASSETS_DIR / "dialog.ogg"


def asset_path(name: str) -> Path:
    """Devuelve la ruta de un recurso incluido en el paquete."""
    return ASSETS_DIR / name
