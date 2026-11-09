"""Servicio de Google Cloud Storage: subida en memoria y Signed URLs.

Nada toca el disco: los bytes van directo de la petición al bucket.
"""
import uuid
from datetime import timedelta
from pathlib import PurePosixPath

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.cloud import storage

from config import settings

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    """Cliente perezoso y reutilizable (usa las credenciales del servicio de Cloud Run)."""
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def _get_bucket() -> storage.Bucket:
    if not settings.gcs_bucket_name:
        raise RuntimeError("Falta la variable de entorno GCS_BUCKET_NAME")
    return _get_client().bucket(settings.gcs_bucket_name)


def _build_blob_name(filename: str | None) -> str:
    ext = PurePosixPath(filename or "").suffix.lower() or ".bin"
    return f"{settings.gcs_upload_folder}/{uuid.uuid4().hex}{ext}"


def public_url(blob_name: str) -> str:
    return f"https://storage.googleapis.com/{settings.gcs_bucket_name}/{blob_name}"


def upload_bytes(data: bytes, filename: str | None, content_type: str | None) -> str:
    """Sube bytes en memoria al bucket y retorna la URL pública.

    El bucket debe tener acceso uniforme y permitir lectura pública
    (allUsers -> roles/storage.objectViewer). El script de deploy lo configura.
    """
    blob = _get_bucket().blob(_build_blob_name(filename))
    blob.cache_control = "public, max-age=31536000"
    blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
    return public_url(blob.name)


def generate_upload_signed_url(filename: str, content_type: str) -> dict:
    """Genera una Signed URL (V4) para que el frontend suba con PUT directo a GCS.

    En Cloud Run las credenciales no tienen clave privada, así que se firma
    vía IAM (signBlob). Requiere que la cuenta de servicio tenga
    roles/iam.serviceAccountTokenCreator sobre sí misma (el deploy lo asigna).
    """
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())

    blob_name = _build_blob_name(filename)
    blob = _get_bucket().blob(blob_name)

    sign_kwargs = {
        "version": "v4",
        "expiration": timedelta(minutes=settings.signed_url_minutes),
        "method": "PUT",
        "content_type": content_type,
    }
    # Con un JSON de cuenta de servicio se firma localmente; en Cloud Run se firma vía IAM.
    if not isinstance(credentials, service_account.Credentials):
        sa_email = getattr(credentials, "service_account_email", None)
        if not sa_email:
            raise RuntimeError(
                "Estas credenciales no pueden firmar URLs. En local usa un JSON de "
                "cuenta de servicio (GOOGLE_APPLICATION_CREDENTIALS) o despliega en Cloud Run."
            )
        sign_kwargs["service_account_email"] = sa_email
        sign_kwargs["access_token"] = credentials.token

    url = blob.generate_signed_url(**sign_kwargs)
    return {
        "upload_url": url,
        "method": "PUT",
        "headers": {"Content-Type": content_type},
        "public_url": public_url(blob_name),
        "expires_in_minutes": settings.signed_url_minutes,
    }
