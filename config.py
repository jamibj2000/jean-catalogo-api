"""Carga de configuración desde variables de entorno (.env en local, env vars en Cloud Run)."""
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()  # En Cloud Run no hay .env: simplemente no hace nada.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Catalogo Cloud API"
    gcs_bucket_name: str = ""            # OBLIGATORIA: nombre del bucket de GCS
    gcs_upload_folder: str = "productos"  # Prefijo/carpeta dentro del bucket
    max_upload_mb: int = 10               # Tamaño máximo de imagen
    signed_url_minutes: int = 15          # Vigencia de las Signed URLs
    cors_origins: str = "*"               # Separados por coma, ej: "https://misitio.netlify.app"
    port: int = 8080                      # Cloud Run inyecta PORT

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
