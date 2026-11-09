"""Catalogo Cloud API — FastAPI lista para Google Cloud Run."""
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from config import settings
from services import storage

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS abierto (Netlify, localhost, etc.). Restringe con CORS_ORIGINS si lo necesitas.
_origins = settings.cors_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,  # credentials + "*" no es válido en CORS
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}


# ---------- Modelos ----------
class Producto(BaseModel):
    id: int
    nombre: str = Field(..., min_length=1, max_length=120)
    precio: float = Field(..., ge=0)
    imagen_url: HttpUrl | None = None


class UploadResponse(BaseModel):
    url: str
    content_type: str
    size_bytes: int


class SignedUrlRequest(BaseModel):
    filename: str
    content_type: str = "image/jpeg"


# ---------- Datos de ejemplo (en memoria; reemplazar por Firestore/Cloud SQL) ----------
CATALOGO: list[Producto] = [
    Producto(id=1, nombre="Camiseta Básica", precio=49900,
             imagen_url="https://storage.googleapis.com/cloud-samples-data/storage/cloud-storage-logo.png"),
    Producto(id=2, nombre="Gorra Clásica", precio=35000, imagen_url=None),
    Producto(id=3, nombre="Taza Cerámica", precio=22000, imagen_url=None),
]


# ---------- Endpoints ----------
@app.get("/", tags=["salud"])
def root():
    return {"status": "ok", "app": settings.app_name, "docs": "/docs"}


@app.get("/health", tags=["salud"])
def health():
    return {"status": "healthy"}


@app.get("/productos", response_model=list[Producto], tags=["catalogo"])
def listar_productos():
    return CATALOGO


@app.post("/productos/imagen", response_model=UploadResponse, tags=["catalogo"])
async def subir_imagen(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Tipo no permitido: {file.content_type}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)  # Lectura en memoria, nunca a disco
    if len(data) > max_bytes:
        raise HTTPException(413, f"La imagen supera {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "Archivo vacío")

    try:
        url = await run_in_threadpool(
            storage.upload_bytes, data, file.filename, file.content_type
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Error subiendo a Cloud Storage: {exc}") from exc

    return UploadResponse(url=url, content_type=file.content_type, size_bytes=len(data))


@app.post("/productos/imagen/signed-url", tags=["catalogo"])
async def signed_url(req: SignedUrlRequest):
    """Devuelve una URL firmada para subir la imagen directo a GCS con PUT."""
    if req.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"Tipo no permitido: {req.content_type}")
    try:
        return await run_in_threadpool(
            storage.generate_upload_signed_url, req.filename, req.content_type
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"No se pudo firmar la URL: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=True)
