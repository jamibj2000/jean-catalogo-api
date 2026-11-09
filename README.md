# catalogo-cloud-api

API ligera de catálogo de productos con FastAPI, pensada para correr 100 % en Google Cloud Run. No guarda archivos en disco: las imágenes van de la petición directo a Google Cloud Storage.

## Estructura

```
catalogo-cloud-api/
├── main.py              # App FastAPI: CORS, modelo Producto, endpoints
├── config.py            # Variables de entorno (pydantic-settings + dotenv)
├── services/
│   ├── __init__.py
│   └── storage.py       # Subida en memoria a GCS + Signed URLs (V4 vía IAM)
├── requirements.txt
├── Dockerfile           # python:3.12-slim, respeta $PORT
├── deploy.ps1           # Deploy en 1 comando (Windows)
├── deploy.sh            # Deploy en 1 comando (Linux/macOS/Cloud Shell)
├── .env.example
├── .dockerignore / .gcloudignore / .gitignore
```

## Deploy (una sola vez instalas gcloud y haces login)

```powershell
gcloud auth login
cd $HOME\Documents\catalogo-cloud-api
.\deploy.ps1 -ProjectId TU-PROYECTO-GCP
```

El script habilita las APIs, crea el bucket `TU-PROYECTO-GCP-catalogo-imagenes` con lectura pública, da permisos a la cuenta de servicio (escritura en el bucket + firma de URLs), configura CORS del bucket y despliega con `gcloud run deploy --source .` (Cloud Build construye el Dockerfile). Al final imprime la URL `/docs`.

Requisito: el proyecto de GCP debe tener la facturación activada.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/productos` | Lista el catálogo |
| POST | `/productos/imagen` | `multipart/form-data` con campo `file`; retorna `{ url }` pública |
| POST | `/productos/imagen/signed-url` | JSON `{ filename, content_type }`; retorna `upload_url` para `PUT` directo a GCS |
| GET | `/health` | Healthcheck |
| GET | `/docs` | Swagger UI |

### Ejemplo desde el frontend (Netlify)

```js
const fd = new FormData();
fd.append("file", input.files[0]);
const r = await fetch(`${API}/productos/imagen`, { method: "POST", body: fd });
const { url } = await r.json();
```

Subida directa con Signed URL:

```js
const s = await fetch(`${API}/productos/imagen/signed-url`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ filename: file.name, content_type: file.type }),
}).then(r => r.json());
await fetch(s.upload_url, { method: "PUT", headers: s.headers, body: file });
// s.public_url ya es la imagen
```

## Local (opcional)

```bash
pip install -r requirements.txt
copy .env.example .env   # pon tu bucket
gcloud auth application-default login
python main.py
```

## Notas

- El catálogo es una lista en memoria de ejemplo; para persistir, conecta Firestore o Cloud SQL.
- Para limitar CORS a tu sitio: `CORS_ORIGINS=https://tusitio.netlify.app` en las env vars del servicio.
# jean-catalogo-api
