# agentic-doc-extraction - Azure Integration Status

## Changes (2026-03-13)
- **Removed Landing AI**: Full removal of `landingai-ade` integration.
- **Azure Primary**: Set Azure Document Intelligence as the default and only provider.
- **Tests**: Updated `tests/test_api.py` to validate the new extraction format.

## Setup Note
Default mock values for Azure endpoint/key were added to `config.py` to allow the application to start and pass tests even without real credentials (useful for CI/local dev).

## Extraction Format
The output now strictly follows:
- `numero_autorizacion`
- `fecha_autorizacion`
- `prestador_autorizado` (nombre, tipo, numero)
- `datos_paciente` (nombre1, nombre2, apellido1, apellido2, tipo, numero)
- `servicios_autorizados` (ubicacion, grupo, items)
- `vigencia`
