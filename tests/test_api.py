from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.authorization import AuthorizationExtraction, AuthorizationResponse
from app.services.document_parser import ParsedDocumentResult


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_parse_endpoint_with_mocked_openai_structured_output() -> None:
    markdown = "AUTORIZACION No.: 1234567890"

    with TestClient(app) as client:
        client.app.state.parser.parse_document = lambda **_: ParsedDocumentResult(
            markdown=markdown,
            chunks=[{"text": "mock"}],
            json_output_path=str(Path("data/parsed/mock.json")),
            markdown_output_path=str(Path("data/parsed/mock.md")),
            model="prebuilt-read",
            provider="azure",
        )

        class _MockExtractor:
            async def extract_authorization(self, _markdown: str) -> tuple[AuthorizationResponse, int, int]:
                return (
                    AuthorizationResponse(
                        authorizations=[AuthorizationExtraction(numero_autorizacion="12345678901234")]
                    ),
                    100,
                    50,
                )

        client.app.state.extractor = _MockExtractor()

        response = client.post(
            "/api/v1/parse",
            files={"file": ("invoice.pdf", BytesIO(b"fake pdf bytes"), "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["authorizations"][0]["numero_autorizacion"] == "12345678901234"


def test_parse_endpoint_filters_null_authorization_number() -> None:
    markdown = "AUTORIZACION No.:"

    with TestClient(app) as client:
        client.app.state.parser.parse_document = lambda **_: ParsedDocumentResult(
            markdown=markdown,
            chunks=[{"text": "mock"}],
            json_output_path=str(Path("data/parsed/mock.json")),
            markdown_output_path=str(Path("data/parsed/mock.md")),
            model="prebuilt-read",
            provider="azure",
        )

        class _MockExtractor:
            async def extract_authorization(self, _markdown: str) -> tuple[AuthorizationResponse, int, int]:
                return (
                    AuthorizationResponse(authorizations=[AuthorizationExtraction()]),
                    100,
                    50,
                )

        client.app.state.extractor = _MockExtractor()

        response = client.post(
            "/api/v1/parse",
            files={"file": ("invoice.pdf", BytesIO(b"fake pdf bytes"), "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json() == {"authorizations": []}
