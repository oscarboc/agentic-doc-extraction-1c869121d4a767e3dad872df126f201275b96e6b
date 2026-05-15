from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

try:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential
except ImportError:  # pragma: no cover - dependency optional at import time
    DocumentIntelligenceClient = None  # type: ignore[assignment]
    AnalyzeDocumentRequest = None  # type: ignore[assignment]
    AzureKeyCredential = None  # type: ignore[assignment]

try:
    from google.cloud import vision as google_vision
    from google.protobuf.json_format import MessageToDict
except ImportError:  # pragma: no cover - dependency optional at import time
    google_vision = None  # type: ignore[assignment]
    MessageToDict = None  # type: ignore[assignment]

ParserProvider = Literal["azure", "google_vision"]


@dataclass(slots=True)
class ParsedDocumentResult:
    markdown: str
    chunks: list[dict[str, Any]]
    json_output_path: str
    markdown_output_path: str
    model: str
    provider: ParserProvider = "google_vision"


class BaseDocumentParser:
    provider: ParserProvider

    def parse_document(self, *, document_path: Path, document_id: str) -> ParsedDocumentResult:
        raise NotImplementedError


class AzureDocumentIntelligenceParser(BaseDocumentParser):
    provider: ParserProvider = "azure"

    def __init__(
        self,
        *,
        output_root: Path,
        endpoint: str,
        key: str,
        model: str = "prebuilt-read",
    ) -> None:
        if (
            DocumentIntelligenceClient is None
            or AzureKeyCredential is None
            or AnalyzeDocumentRequest is None
        ):
            raise RuntimeError(
                "Azure Document Intelligence dependencies are not installed. "
                "Install azure-ai-documentintelligence and azure-core."
            )

        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.endpoint = endpoint
        self.key = key
        self.model = model
        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key),
        )

    def parse_document(self, *, document_path: Path, document_id: str) -> ParsedDocumentResult:
        output_dir = self.output_root / document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        file_bytes = document_path.read_bytes()
        poller = self.client.begin_analyze_document(
            self.model,
            AnalyzeDocumentRequest(bytes_source=file_bytes),
            output_content_format="markdown",
        )
        result = poller.result()

        markdown = getattr(result, "content", "") or ""
        markdown_output_path = output_dir / f"{document_path.stem}.md"
        markdown_output_path.write_text(markdown, encoding="utf-8")

        raw_json_path = output_dir / f"{document_path.stem}.azure_parse_output.json"
        raw_payload = self._to_jsonable(result)
        raw_json_path.write_text(
            json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return ParsedDocumentResult(
            markdown=markdown,
            chunks=self._extract_chunks(result),
            json_output_path=str(raw_json_path),
            markdown_output_path=str(markdown_output_path),
            model=self.model,
            provider=self.provider,
        )

    def _extract_chunks(self, result: Any) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for page in getattr(result, "pages", []) or []:
            page_number = getattr(page, "page_number", None)
            for line in getattr(page, "lines", []) or []:
                polygon = getattr(getattr(line, "polygon", None), "__iter__", None)
                polygon_points = list(line.polygon) if polygon else None
                chunks.append(
                    {
                        "type": "line",
                        "page_number": page_number,
                        "content": getattr(line, "content", None),
                        "polygon": polygon_points,
                    }
                )

        if not chunks and getattr(result, "content", None):
            chunks.append({"type": "document", "content": result.content})

        return chunks

    def _to_jsonable(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "as_dict"):
            return result.as_dict()
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return {"content": getattr(result, "content", "")}


_PDF_MIME = "application/pdf"


class GoogleCloudVisionParser(BaseDocumentParser):
    provider: ParserProvider = "google_vision"

    def __init__(
        self,
        *,
        output_root: Path,
        credentials_file: str | None = None,
    ) -> None:
        if google_vision is None:
            raise RuntimeError(
                "Google Cloud Vision dependencies are not installed. "
                "Install google-cloud-vision."
            )
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

        if credentials_file:
            self.client = google_vision.ImageAnnotatorClient.from_service_account_file(
                credentials_file
            )
        else:
            # Falls back to GOOGLE_APPLICATION_CREDENTIALS env var or ADC
            self.client = google_vision.ImageAnnotatorClient()

    def parse_document(self, *, document_path: Path, document_id: str) -> ParsedDocumentResult:
        output_dir = self.output_root / document_id
        output_dir.mkdir(parents=True, exist_ok=True)

        file_bytes = document_path.read_bytes()
        suffix = document_path.suffix.lower()

        if suffix == ".pdf":
            full_text, chunks, raw_payload = self._process_pdf(file_bytes)
        else:
            full_text, chunks, raw_payload = self._process_image(file_bytes)

        markdown_output_path = output_dir / f"{document_path.stem}.md"
        markdown_output_path.write_text(full_text, encoding="utf-8")

        raw_json_path = output_dir / f"{document_path.stem}.google_vision_output.json"
        raw_json_path.write_text(
            json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return ParsedDocumentResult(
            markdown=full_text,
            chunks=chunks,
            json_output_path=str(raw_json_path),
            markdown_output_path=str(markdown_output_path),
            model="document-text-detection",
            provider=self.provider,
        )

    def _process_image(
        self, file_bytes: bytes
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        image = google_vision.Image(content=file_bytes)
        response = self.client.document_text_detection(image=image)
        full_text = getattr(response.full_text_annotation, "text", "") or ""
        chunks = self._extract_chunks(response.full_text_annotation, page_number=1)
        raw_payload = MessageToDict(response._pb)  # type: ignore[union-attr]
        return full_text, chunks, raw_payload

    def _process_pdf(
        self, file_bytes: bytes
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        input_config = google_vision.InputConfig(content=file_bytes, mime_type=_PDF_MIME)
        feature = google_vision.Feature(type_=google_vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        request = google_vision.AnnotateFileRequest(
            input_config=input_config,
            features=[feature],
        )
        batch_response = self.client.batch_annotate_files(requests=[request])

        full_text_parts: list[str] = []
        chunks: list[dict[str, Any]] = []
        raw_responses: list[dict[str, Any]] = []

        for file_response in batch_response.responses:
            for page_num, page_response in enumerate(file_response.responses, start=1):
                page_text = getattr(page_response.full_text_annotation, "text", "") or ""
                full_text_parts.append(page_text)
                chunks.extend(
                    self._extract_chunks(page_response.full_text_annotation, page_number=page_num)
                )
                raw_responses.append(MessageToDict(page_response._pb))  # type: ignore[union-attr]

        return "\n\n".join(full_text_parts), chunks, {"responses": raw_responses}

    def _extract_chunks(
        self, text_annotation: Any, *, page_number: int
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for page in getattr(text_annotation, "pages", []) or []:
            for block in getattr(page, "blocks", []) or []:
                block_text_parts: list[str] = []
                for paragraph in getattr(block, "paragraphs", []) or []:
                    words = getattr(paragraph, "words", []) or []
                    para_text = " ".join(
                        "".join(
                            getattr(symbol, "text", "")
                            for symbol in getattr(word, "symbols", [])
                        )
                        for word in words
                    )
                    block_text_parts.append(para_text)

                bounding_box = getattr(block, "bounding_box", None)
                vertices = (
                    [{"x": v.x, "y": v.y} for v in getattr(bounding_box, "vertices", [])]
                    if bounding_box
                    else None
                )
                chunks.append(
                    {
                        "type": "block",
                        "page_number": page_number,
                        "content": "\n".join(block_text_parts),
                        "bounding_box": vertices,
                    }
                )

        if not chunks and getattr(text_annotation, "text", None):
            chunks.append({"type": "document", "content": text_annotation.text})

        return chunks


class DocumentParserRouter:
    def __init__(
        self, *, default_provider: ParserProvider, parsers: dict[ParserProvider, BaseDocumentParser]
    ) -> None:
        self.default_provider = default_provider
        self.parsers = parsers

    def parse_document(
        self,
        *,
        document_path: Path,
        document_id: str,
        provider: ParserProvider | None = None,
    ) -> ParsedDocumentResult:
        selected = provider or self.default_provider
        parser = self.parsers.get(selected)
        if parser is None:
            available = ", ".join(sorted(self.parsers.keys()))
            msg = f"Parser provider '{selected}' is not available or not configured."
            if available:
                msg += f" Available providers: {available}"
            else:
                msg += " No providers are currently configured."
            raise ValueError(msg)
        return parser.parse_document(document_path=document_path, document_id=document_id)
