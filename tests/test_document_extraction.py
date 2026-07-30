from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.document_parser import (
    AzureDocumentIntelligenceParser,
    DocumentParserRouter,
)
from app.services.openai_extractor import OpenAIExtractorService


async def process_file(file_path, parser, extractor, settings):
    path = Path(file_path)
    if not path.exists():
        pytest.skip(f"Archivo no encontrado: {file_path}")

    document_id = path.stem

    try:
        parsed = parser.parse_document(
            document_path=path,
            document_id=document_id,
        )

        extraction, tokens_in, tokens_out = await extractor.extract_authorization(parsed.markdown)

        # Validations
        valid_auths = []
        anomalies = []

        auths = extraction.authorizations

        for i, auth in enumerate(auths):
            auth_num = auth.numero_autorizacion

            # 1. No nulls in critical fields
            if auth_num is None:
                anomalies.append(f"Auth {i}: numero_autorizacion es NULL")
                continue

            # 2. 14 digits validation
            clean_num = "".join(filter(str.isdigit, str(auth_num)))
            if len(clean_num) != 14:
                anomalies.append(
                    f"Auth {i}: numero_autorizacion '{auth_num}' no tiene 14 dígitos "
                    f"(tiene {len(clean_num)})"
                )
            else:
                valid_auths.append(auth)

        return {
            "file": path.name,
            "success": True,
            "count": len(auths),
            "valid_count": len(valid_auths),
            "anomalies": anomalies,
            "data": [a.model_dump() for a in valid_auths],
        }

    except Exception as e:
        return {"file": path.name, "success": False, "error": str(e)}


@pytest.fixture(scope="session")
def settings():
    try:
        return Settings()
    except ValidationError as e:
        pytest.skip(f"Settings inválidos: {e}")


@pytest.fixture(scope="session")
def parser(settings):
    from app.services.document_parser import GoogleCloudVisionParser

    parsers = {}

    if settings.azure_document_intelligence_endpoint and settings.azure_document_intelligence_key:
        parsers["azure"] = AzureDocumentIntelligenceParser(
            output_root=settings.parse_output_dir,
            endpoint=settings.azure_document_intelligence_endpoint,
            key=settings.azure_document_intelligence_key,
            model=settings.azure_document_intelligence_model,
        )

    try:
        parsers["google_vision"] = GoogleCloudVisionParser(
            output_root=settings.parse_output_dir,
            credentials_file=settings.google_vision_credentials_file,
        )
    except Exception:
        pass

    if not parsers:
        pytest.skip("Ningún proveedor de OCR configurado.")

    default_provider = (
        settings.ocr_provider if settings.ocr_provider in parsers else next(iter(parsers), "azure")
    )

    return DocumentParserRouter(
        default_provider=default_provider,
        parsers=parsers,
    )


@pytest.fixture(scope="session")
def extractor(settings):
    # Skip if OpenAI config missing
    if not settings.openai_api_key:
        pytest.skip("OpenAI API key no configurada.")
    return OpenAIExtractorService(settings)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_path",
    [
        "/Users/diego/Downloads/Telegram Desktop/PDE_800084362_FEV189529.pdf",
    ],
)
async def test_document_extraction(file_path, parser, extractor, settings):
    result = await process_file(file_path, parser, extractor, settings)

    assert result["success"] is True
    assert "count" in result
    assert "valid_count" in result
    assert "anomalies" in result

    # Optional: fail if there are anomalies
    if result["anomalies"]:
        pytest.fail("Anomalías encontradas:\n" + "\n".join(result["anomalies"]))
