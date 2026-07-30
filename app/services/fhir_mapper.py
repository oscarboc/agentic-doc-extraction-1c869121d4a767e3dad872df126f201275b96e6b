"""
FHIR Patient RDA mapper – converts extracted PatientData to FHIR R4 JSON
aligned with the Colombian RDA (Resumen Digital de Atención) profile:
  https://fhir.minsalud.gov.co/rda/StructureDefinition/PatientRDA

Reference example:
  https://vulcano.ihcecol.gov.co/Patient-92a8e277-af20-4854-a3fb-02cbe9fb8d49.json
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.patient import PatientData

_FHIR_PROFILE = "https://fhir.minsalud.gov.co/rda/StructureDefinition/PatientRDA"

# --- Extension URLs -----------------------------------------------------------
EXT_NATIONALITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionPatientNationality"
EXT_BIRTH_PLACE = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionBirthPlace"
EXT_ETHNICITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionPatientEthnicity"
EXT_ETHNIC_COMMUNITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionPatientEthnicCommunity"
EXT_DISABILITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionPatientDisability"
EXT_GENDER_IDENTITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionPatientGenderIdentity"
EXT_BIOLOGICAL_GENDER = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionBiologicalGender"
EXT_BIRTH_TIME = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionBirthTime"
EXT_RESIDENCE_ZONE = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionResidenceZone"
EXT_DIVIPOLA_MUNICIPALITY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionDivipolaMunicipality"
EXT_COUNTRY_CODE = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionCountryCode"
EXT_FATHERS_FAMILY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionFathersFamilyName"
EXT_MOTHERS_FAMILY = "https://fhir.minsalud.gov.co/rda/StructureDefinition/ExtensionMothersFamilyName"

# --- Code Systems (matching official RDA canonical URLs) ----------------------
CS_PERSON_ID_INTL = "http://terminology.hl7.org/CodeSystem/v2-0203"
CS_PERSON_ID_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianPersonIdentifier"
NS_RNEC = "https://fhir.minsalud.gov.co/rda/NamingSystem/RNEC"
CS_MARITAL = "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus"
CS_ISO31661 = "https://fhir.minsalud.gov.co/rda/CodeSystem/ISO31661"
CS_ETHNICITY_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianEthnicGroup"
CS_DISABILITY_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianDisabilityClassification"
CS_RESIDENCE_ZONE_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianResidenceZone"
CS_DIVIPOLA = "https://fhir.minsalud.gov.co/rda/CodeSystem/DIVIPOLA"
CS_GENDER_GROUP_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianGenderGroup"
CS_GENDER_IDENTITY_CO = "https://fhir.minsalud.gov.co/rda/CodeSystem/ColombianGenderIdentity"

# --- Identifier type mappings -------------------------------------------------
_ID_TYPE_MAP: dict[str, dict[str, str]] = {
    "cedula ciudadania": {"code": "CC", "display": "Cédula ciudadanía"},
    "cédula de ciudadanía": {"code": "CC", "display": "Cédula ciudadanía"},
    "cedula de ciudadania": {"code": "CC", "display": "Cédula ciudadanía"},
    "c.c.": {"code": "CC", "display": "Cédula ciudadanía"},
    "cc": {"code": "CC", "display": "Cédula ciudadanía"},
    "tarjeta identidad": {"code": "TI", "display": "Tarjeta de identidad"},
    "tarjeta de identidad": {"code": "TI", "display": "Tarjeta de identidad"},
    "t.i.": {"code": "TI", "display": "Tarjeta de identidad"},
    "ti": {"code": "TI", "display": "Tarjeta de identidad"},
    "registro civil": {"code": "RC", "display": "Registro civil"},
    "cedula extranjeria": {"code": "CE", "display": "Cédula de extranjería"},
    "cédula de extranjería": {"code": "CE", "display": "Cédula de extranjería"},
    "pasaporte": {"code": "PA", "display": "Pasaporte"},
    "nit": {"code": "NIT", "display": "NIT"},
    "doc. id.": {"code": "CC", "display": "Cédula ciudadanía"},
}

# --- Gender mapping -----------------------------------------------------------
_GENDER_MAP: dict[str, str] = {
    "f": "female",
    "femenino": "female",
    "m": "male",
    "masculino": "male",
}

# --- Marital status mapping ---------------------------------------------------
_MARITAL_MAP: dict[str, dict[str, str]] = {
    "soltero": {"code": "S", "display": "Never Married"},
    "soltero(a)": {"code": "S", "display": "Never Married"},
    "soltera": {"code": "S", "display": "Never Married"},
    "casado": {"code": "M", "display": "Married"},
    "casado(a)": {"code": "M", "display": "Married"},
    "casada": {"code": "M", "display": "Married"},
    "u. libre": {"code": "U", "display": "unmarried"},
    "union libre": {"code": "U", "display": "unmarried"},
    "unión libre": {"code": "U", "display": "unmarried"},
    "viudo": {"code": "W", "display": "Widowed"},
    "viudo(a)": {"code": "W", "display": "Widowed"},
    "viuda": {"code": "W", "display": "Widowed"},
    "divorciado": {"code": "D", "display": "Divorced"},
    "divorciado(a)": {"code": "D", "display": "Divorced"},
    "divorciada": {"code": "D", "display": "Divorced"},
    "separado": {"code": "L", "display": "Legally Separated"},
    "separado(a)": {"code": "L", "display": "Legally Separated"},
}

# --- Ethnicity heuristic mapping (text → RDA code) ----------------------------
_ETHNICITY_MAP: dict[str, dict[str, str]] = {
    "indígena": {"code": "1", "display": "Indígena"},
    "indigena": {"code": "1", "display": "Indígena"},
    "gitano": {"code": "2", "display": "Gitano(a) o Rom"},
    "rom": {"code": "2", "display": "Gitano(a) o Rom"},
    "raizal": {"code": "3", "display": "Raizal del archipiélago de San Andrés, Providencia y Santa Catalina"},
    "palenquero": {"code": "4", "display": "Palenquero(a) de San Basilio"},
    "negro": {"code": "5", "display": "Negro(a) o mulato(a) o afrocolombiano(a) o afrodescendiente"},
    "afro": {"code": "5", "display": "Negro(a) o mulato(a) o afrocolombiano(a) o afrodescendiente"},
    "afrocolombiano": {"code": "5", "display": "Negro(a) o mulato(a) o afrocolombiano(a) o afrodescendiente"},
    "mestizo": {"code": "6", "display": "Mestizo"},
    "blanco": {"code": "6", "display": "Mestizo"},
    "otro": {"code": "6", "display": "Mestizo"},
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _map_id_type(raw: str | None) -> dict[str, str]:
    key = _norm(raw)
    return _ID_TYPE_MAP.get(key, {"code": "NN", "display": raw or "Desconocido"})


def _map_gender(raw: str | None) -> str:
    return _GENDER_MAP.get(_norm(raw), "unknown")


def _map_marital_status(raw: str | None) -> dict[str, Any] | None:
    key = _norm(raw)
    mapped = _MARITAL_MAP.get(key)
    if mapped:
        return {
            "coding": [
                {"system": CS_MARITAL, "code": mapped["code"], "display": mapped["display"]}
            ],
            "text": raw,
        }
    if raw:
        return {"text": raw}
    return None


def _map_ethnicity(raw: str | None) -> dict[str, str] | None:
    if not raw:
        return None
    key = _norm(raw)
    return _ETHNICITY_MAP.get(key, {"code": "6", "display": raw.strip().title()})


def _split_given(full_name: str | None) -> list[str]:
    """Split combined given name string into array like ['Mónica', 'María']."""
    if not full_name:
        return []
    parts = full_name.strip().split()
    return parts if parts else []


def _parse_birthdate(raw: str | None) -> str | None:
    """Normalize to YYYY-MM-DD."""
    if not raw or raw.strip() in ("", "00", "0000-00-00"):
        return None
    raw = raw.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", raw)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    }
    m2 = re.match(r"^(\d{1,2})[/-](\w+)[/-](\d{4})$", raw)
    if m2:
        mes = meses.get(m2.group(2).lower(), "01")
        return f"{m2.group(3)}-{mes}-{m2.group(1).zfill(2)}"
    return raw


def _map_telecoms(data: PatientData) -> list[dict[str, str]]:
    telecoms: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(phone: str | None, use: str) -> None:
        if not phone or phone.strip() in ("", "00", "0", "000", "0000"):
            return
        val = re.sub(r"\D", "", phone)
        if not val or val in seen:
            return
        seen.add(val)
        telecoms.append({"system": "phone", "value": val, "use": use})

    _add(data.telefono_casa, "home")
    _add(data.telefono_movil, "mobile")
    _add(data.telefono_trabajo, "work")

    if data.email and data.email.strip():
        telecoms.append({"system": "email", "value": data.email.strip(), "use": "home"})

    return telecoms


def _build_extensions(data: PatientData) -> list[dict[str, Any]]:
    extensions: list[dict[str, Any]] = []

    # Nationality
    if data.nacionalidad:
        extensions.append({
            "url": EXT_NATIONALITY,
            "valueCoding": {
                "system": CS_ISO31661,
                "code": "170",
                "display": "Colombia",
            },
        })

    # BirthPlace
    if data.ciudad or data.departamento:
        bp: dict[str, Any] = {"url": EXT_BIRTH_PLACE, "valueAddress": {"country": "Colombia"}}
        if data.ciudad:
            bp["valueAddress"]["city"] = data.ciudad
        if data.departamento:
            bp["valueAddress"]["state"] = data.departamento
        extensions.append(bp)

    # Ethnicity
    eth = _map_ethnicity(data.etnia)
    if eth:
        extensions.append({
            "url": EXT_ETHNICITY,
            "valueCoding": {
                "system": CS_ETHNICITY_CO,
                "code": eth["code"],
                "display": eth["display"],
            },
        })

    # Ethnic community (if not captured by ethnicity itself)
    if data.grupo_poblacional and _norm(data.grupo_poblacional) not in ("", "otro grupo poblacional", "ninguno"):
        extensions.append({
            "url": EXT_ETHNIC_COMMUNITY,
            "valueString": data.grupo_poblacional,
        })

    # Disability (default: sin discapacidad)
    extensions.append({
        "url": EXT_DISABILITY,
        "valueCoding": {
            "system": CS_DISABILITY_CO,
            "code": "08",
            "display": "Sin discapacidad",
        },
    })

    # GenderIdentity
    gender = _map_gender(data.sexo)
    gid_code = "02" if gender == "female" else "01" if gender == "male" else "03"
    gid_display = "Femenino" if gender == "female" else "Masculino" if gender == "male" else "No informa"
    extensions.append({
        "url": EXT_GENDER_IDENTITY,
        "valueCoding": {
            "system": CS_GENDER_IDENTITY_CO,
            "code": gid_code,
            "display": gid_display,
        },
    })

    return extensions


def patient_data_to_fhir(data: PatientData) -> dict[str, Any]:
    """Convert extracted PatientData → FHIR R4 Patient RDA JSON (Colombian profile)."""

    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "meta": {
            "profile": [_FHIR_PROFILE],
        },
        "active": True,
        "deceasedBoolean": False,
    }

    # --- identifier: NationalPersonIdentifier ---------------------------------
    id_type = _map_id_type(data.tipo_identificacion)
    nid_value = _norm(data.numero_identificacion)
    if nid_value and nid_value not in ("0", "00", "000"):
        resource["identifier"] = [
            {
                "id": "NationalPersonIdentifier-0",
                "use": "official",
                "type": {
                    "coding": [
                        {
                            "system": CS_PERSON_ID_INTL,
                            "code": "PN",
                            "display": "Person number",
                        },
                        {
                            "system": CS_PERSON_ID_CO,
                            "code": id_type["code"],
                            "display": id_type["display"],
                        },
                    ]
                },
                "system": NS_RNEC,
                "value": data.numero_identificacion,
            }
        ]

    # --- name: OfficialPatientName ---------------------------------------------
    apellido1 = (data.apellido1 or "").strip()
    apellido2 = (data.apellido2 or "").strip()
    family = f"{apellido1} {apellido2}".strip()

    nombres_str = (data.nombre1 or "").strip()
    if data.nombre2:
        nombres_str = f"{nombres_str} {data.nombre2.strip()}"
    nombres_str = nombres_str.strip()
    given_list = _split_given(nombres_str)

    official_name: dict[str, Any] = {
        "use": "official",
        "family": family,
    }

    # FathersFamilyName + MothersFamilyName extensions on _family
    if apellido1 or apellido2:
        fam_exts: list[dict[str, str]] = []
        if apellido1:
            fam_exts.append({"url": EXT_FATHERS_FAMILY, "valueString": apellido1})
        if apellido2:
            fam_exts.append({"url": EXT_MOTHERS_FAMILY, "valueString": apellido2})
        official_name["_family"] = {"extension": fam_exts}

    if given_list:
        official_name["given"] = given_list

    resource["name"] = [official_name]

    # --- telecom ----------------------------------------------------------------
    telecoms = _map_telecoms(data)
    if telecoms:
        resource["telecom"] = telecoms

    # --- gender + _gender extension --------------------------------------------
    gender = _map_gender(data.sexo)
    resource["gender"] = gender

    bg_code = "02" if gender == "female" else "01" if gender == "male" else "03"
    bg_display = "Mujer" if gender == "female" else "Hombre" if gender == "male" else "Intersexual o Indeterminado"
    resource["_gender"] = {
        "extension": [
            {
                "url": EXT_BIOLOGICAL_GENDER,
                "valueCoding": {
                    "system": CS_GENDER_GROUP_CO,
                    "code": bg_code,
                    "display": bg_display,
                },
            }
        ]
    }

    # --- birthDate + _birthDate ------------------------------------------------
    bd = _parse_birthdate(data.fecha_nacimiento)
    if bd:
        resource["birthDate"] = bd
        resource["_birthDate"] = {
            "extension": [
                {"url": EXT_BIRTH_TIME}
            ]
        }

    # --- address: HomeAddress --------------------------------------------------
    address: dict[str, Any] = {
        "id": "HomeAddress-0",
        "use": "home",
        "type": "physical",
    }

    # ResidenceZone extension (01=Urbana, 02=Rural, default=Urbana)
    address["extension"] = [
        {
            "url": EXT_RESIDENCE_ZONE,
            "valueCoding": {
                "system": CS_RESIDENCE_ZONE_CO,
                "code": "01",
                "display": "Urbana",
            },
        }
    ]

    addr_parts: list[str] = []
    if data.direccion:
        addr_parts.append(data.direccion)
    if data.barrio:
        addr_parts.append(f"Barrio {data.barrio}")
    if addr_parts:
        address["line"] = [", ".join(addr_parts)]

    city = data.municipio or data.ciudad
    if city:
        address["city"] = city
        address["_city"] = {
            "extension": [
                {
                    "url": EXT_DIVIPOLA_MUNICIPALITY,
                    "valueCoding": {
                        "system": CS_DIVIPOLA,
                        "code": "00000",
                    },
                }
            ]
        }

    if data.departamento:
        address["district"] = data.departamento

    address["country"] = "Colombia"
    address["_country"] = {
        "extension": [
            {
                "url": EXT_COUNTRY_CODE,
                "valueCoding": {
                    "system": CS_ISO31661,
                    "code": "170",
                },
            }
        ]
    }

    resource["address"] = [address]

    # --- maritalStatus ---------------------------------------------------------
    ms = _map_marital_status(data.estado_civil)
    if ms:
        resource["maritalStatus"] = ms

    # --- contact (acudiente) ---------------------------------------------------
    if data.acudiente and _norm(data.acudiente) not in ("solo", "no tiene", "no refiere", "ninguno", "negativo"):
        contact: dict[str, Any] = {
            "relationship": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0131",
                            "code": "C",
                            "display": "Emergency Contact",
                        }
                    ]
                }
            ],
            "name": {"text": data.acudiente},
        }
        if data.telefono_acudiente and _norm(data.telefono_acudiente) not in ("00", "0", ""):
            contact["telecom"] = [
                {"system": "phone", "value": re.sub(r"\D", "", data.telefono_acudiente)}
            ]
        resource["contact"] = [contact]

    # --- managingOrganization (EPS) --------------------------------------------
    if data.eps_entidad:
        resource["managingOrganization"] = {
            "display": data.eps_entidad,
        }

    # --- communication (language) ----------------------------------------------
    resource["communication"] = [
        {
            "language": {
                "coding": [
                    {"system": "urn:ietf:bcp:47", "code": "es", "display": "Spanish"}
                ]
            }
        }
    ]

    # --- extensions (nationality, birthPlace, ethnicity, disability, genderIdentity)
    resource["extension"] = _build_extensions(data)

    return resource
