from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class PatientPhoneData(BaseModel):
    casa: str | None = Field(default=None, description="Telefono fijo o de casa")
    movil: str | None = Field(default=None, description="Telefono celular o movil")
    trabajo: str | None = Field(default=None, description="Telefono laboral")
    otros: list[str] = Field(default_factory=list)

    @field_validator("casa", "movil", "trabajo", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _blank_to_none(value)


class DemographicDatum(BaseModel):
    campo: str
    valor: str


class PatientData(BaseModel):
    """Datos demográficos del paciente extraídos de una historia clínica."""

    nombre_completo: str | None = None
    apellido1: str | None = None
    apellido2: str | None = None
    nombre1: str | None = None
    nombre2: str | None = None
    tipo_identificacion: str | None = None
    numero_identificacion: str | None = None
    fecha_nacimiento: str | None = None
    edad: str | None = None
    sexo: str | None = None
    direccion: str | None = None
    barrio: str | None = None
    telefonos: PatientPhoneData = Field(default_factory=PatientPhoneData)
    telefono_casa: str | None = None
    telefono_movil: str | None = None
    telefono_trabajo: str | None = None
    email: str | None = None
    estado_civil: str | None = None
    eps_entidad: str | None = None
    regimen: str | None = None
    tipo_afiliacion: str | None = None
    ocupacion: str | None = None
    ciudad_municipio: str | None = None
    ciudad: str | None = None
    municipio: str | None = None
    departamento: str | None = None
    grupo_sanguineo: str | None = None
    etnia: str | None = None
    grupo_poblacional: str | None = None
    nacionalidad: str | None = None
    religion: str | None = None
    acudiente: str | None = None
    telefono_acudiente: str | None = None
    parentesco_acudiente: str | None = None
    otros_datos_demograficos: list[DemographicDatum] = Field(default_factory=list)

    @field_validator(
        "nombre_completo",
        "apellido1",
        "apellido2",
        "nombre1",
        "nombre2",
        "tipo_identificacion",
        "numero_identificacion",
        "fecha_nacimiento",
        "edad",
        "sexo",
        "direccion",
        "barrio",
        "telefono_casa",
        "telefono_movil",
        "telefono_trabajo",
        "email",
        "estado_civil",
        "eps_entidad",
        "regimen",
        "tipo_afiliacion",
        "ocupacion",
        "ciudad_municipio",
        "ciudad",
        "municipio",
        "departamento",
        "grupo_sanguineo",
        "etnia",
        "grupo_poblacional",
        "nacionalidad",
        "religion",
        "acudiente",
        "telefono_acudiente",
        "parentesco_acudiente",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def fill_derived_patient_fields(self) -> "PatientData":
        if not self.nombre_completo:
            name_parts = [self.nombre1, self.nombre2, self.apellido1, self.apellido2]
            self.nombre_completo = " ".join(part for part in name_parts if part) or None

        if not self.ciudad_municipio:
            city_parts = [self.ciudad, self.municipio]
            self.ciudad_municipio = " / ".join(part for part in city_parts if part) or None

        if self.telefonos.casa and not self.telefono_casa:
            self.telefono_casa = self.telefonos.casa
        if self.telefono_casa and not self.telefonos.casa:
            self.telefonos.casa = self.telefono_casa

        if self.telefonos.movil and not self.telefono_movil:
            self.telefono_movil = self.telefonos.movil
        if self.telefono_movil and not self.telefonos.movil:
            self.telefonos.movil = self.telefono_movil

        if self.telefonos.trabajo and not self.telefono_trabajo:
            self.telefono_trabajo = self.telefonos.trabajo
        if self.telefono_trabajo and not self.telefonos.trabajo:
            self.telefonos.trabajo = self.telefono_trabajo

        return self


class PatientExtractionResponse(BaseModel):
    """Output estructurado del LLM: contiene los datos del paciente extraídos."""

    patient: PatientData = Field(default_factory=PatientData)


class PatientDataResponse(BaseModel):
    """Respuesta completa del endpoint /api/v1/extract-patient."""

    document_id: str
    filename: str
    content_type: str | None
    size_bytes: int
    created_at: datetime
    provider: str
    model: str
    extracted_pages: int
    chunk_count: int
    tokens_input: int
    tokens_output: int
    patient: PatientData = Field(default_factory=PatientData)
