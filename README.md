# agentic-doc-extraction

Backend en **FastAPI** para parsear documentos y extraer datos estructurados de autorizaciones médicas.

Actualmente soporta dos proveedores de OCR/parseo:

- **Azure AI Document Intelligence** (`prebuilt-read`)

## Endpoints activos

- `GET /health`
- `POST /api/v1/parse`

## Ejecutar

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Variables de entorno

### Azure Document Intelligence

```bash
export AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<tu-resource>.cognitiveservices.azure.com/"
export AZURE_DOCUMENT_INTELLIGENCE_KEY="<tu-key>"
# opcional
export DOC_EXTRACTION_AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-read
```

## Qué hace cada endpoint

### `POST /api/v1/parse`

Recibe un archivo, lo guarda localmente, lo parsea con el proveedor seleccionado y luego extrae campos útiles de autorizaciones médica:

- `authorization_numbers`
- `primary_authorization_number`
- `solicitud_numbers`
- `patient_name`
- `patient_document_id`
- `eps`
- `ips`
- `cups_codes`
- `service_description`
- `observacion`
- `vigencia`

## Archivos generados

- uploads: `data/uploads/`
- parse outputs: `data/parsed/<document_id>/`
- markdown: `data/parsed/<document_id>/<archivo>.md`

## Tests y calidad

```bash
uv run python -m pytest
uv run python -m ruff check .
uv run python -m ruff format --check .
```
# agentic-doc-extraction
