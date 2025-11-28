"""Application constants and field definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# === SDS SECTIONS (ABNT NBR 14725) ===
SDS_SECTIONS: Final[dict[int, str]] = {
    1: "Identificação do produto e da empresa",
    2: "Identificação de perigos",
    3: "Composição e informações sobre os ingredientes",
    4: "Medidas de primeiros-socorros",
    5: "Medidas de combate a incêndio",
    6: "Medidas de controle para derramamento ou vazamento",
    7: "Manuseio e armazenamento",
    8: "Controle de exposição e proteção individual",
    9: "Propriedades físicas e químicas",
    10: "Estabilidade e reatividade",
    11: "Informações toxicológicas",
    12: "Informações ecológicas",
    13: "Considerações sobre destinação final",
    14: "Informações sobre transporte",
    15: "Informações sobre regulamentações",
    16: "Outras informações",
}

# === SUPPORTED FILE FORMATS ===
SUPPORTED_FORMATS: Final[dict[str, str]] = {
    ".pdf": "PDF",
    ".docx": "Word",
    ".doc": "Word (Legacy)",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".txt": "Text",
    ".html": "HTML",
    ".htm": "HTML",
    ".csv": "CSV",
    ".xlsx": "Excel",
    ".xls": "Excel (Legacy)",
}


# === EXTRACTION FIELD DEFINITIONS ===
@dataclass(frozen=True)
class FieldDefinition:
    """Definition of a field to extract from SDS documents."""

    name: str
    label_pt: str
    label_en: str
    section: int | None  # Primary SDS section where found
    pattern: re.Pattern[str] | None  # Regex pattern for heuristic extraction
    required: bool = True
    prompt_template: str = ""


# Compiled regex patterns for heuristic extraction
PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "un_number": re.compile(
        r"(?:UN|ONU)[\s#:;\-]{0,3}(\d{4})"
        r"|\b(\d{4})\b(?=.*(?:classe|risco|transporte))",
        re.IGNORECASE | re.VERBOSE,
    ),
    "cas_number": re.compile(
        r"\b(\d{2,7}-\d{2}-\d)\b",
    ),
    "hazard_class": re.compile(
        r"classe\s*(?:de\s*)?(?:risco|perigo)?\s*[:\-]?\s*(\d(?:\.\d)?)",
        re.IGNORECASE,
    ),
    "product_name": re.compile(
        r"(?:nome\s*(?:comercial|do\s+produto|químico)|"
        r"identifica(?:ç|c)[aã]o\s+do\s+produto|"
        r"identificador\s+do\s+produto|"
        r"product\s+name|"
        r"chemical\s+name|"
        r"produto)\s*[:\-]\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9\s\-,()./%]+(?:[A-Za-zÀ-ÿ]|\d{1,3}%)[^\n]{0,80})",
        re.IGNORECASE,
    ),
    "manufacturer": re.compile(
        r"(?:fabricante|fabricado\s+por|"
        r"fornecedor(?:\\/distribuidor)?|"
        r"manufacturer|"
        r"empresa|raz[aã]o\s+social)\s*[:\-]\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9\s\-,&.]+?(?:LTDA|S\\.?A\\.?|INC|LLC|GMBH|LTD)?[^\n]{0,100})",
        re.IGNORECASE,
    ),
    "packing_group": re.compile(
        r"grupo\s*(?:de)?\s*embalagem\s*[:\-]?\s*(I{1,3}|III|II|I|1|2|3)\b",
        re.IGNORECASE,
    ),
    "incompatibilities": re.compile(
        r"(?:incompatíve[li]s?\s*(?:com)?|"
        r"evitar\s+contato\s+com|"
        r"materiais?\s+(?:a\s+)?evitar|"
        r"reage\s+(?:perigosamente\s+)?com|"
        r"incompatible\s+(?:with|materials)|"
        r"não\s+(?:misturar|armazenar)\s+(?:com|junto))\s*[:\-]?\s*([^\n]{5,400})",
        re.IGNORECASE,
    ),
    "h_statements": re.compile(
        r"(H\d{3}(?:\s*\+\s*H\d{3})*)",
        re.IGNORECASE,
    ),
    "p_statements": re.compile(
        r"(P\d{3}(?:\s*\+\s*P\d{3})*)",
        re.IGNORECASE,
    ),
}


# Field definitions for extraction
EXTRACTION_FIELDS: Final[list[FieldDefinition]] = [
    FieldDefinition(
        name="product_name",
        label_pt="Nome do Produto",
        label_en="Product Name",
        section=1,
        pattern=PATTERNS["product_name"],
        prompt_template=(
              "Extract the PRIMARY CHEMICAL product name from this SDS section.\n"
              "Look for: Product name, Chemical name, Trade name.\n"
              "Return the MAIN chemical name, NOT brand names, codes, or catalog numbers.\n\n"
              "Examples:\n"
              "- 'Ácido Sulfúrico 98%' → 'Ácido Sulfúrico'\n"
              "- 'ACME Brand H2SO4' → 'Ácido Sulfúrico'\n"
              "- 'Ethanol 95%' → 'Ethanol'\n\n"
              "Text:\n{text}\n\n"
              "Return ONLY the chemical name. If not found, return 'NOT_FOUND'."
        ),
    ),
    FieldDefinition(
        name="manufacturer",
        label_pt="Fabricante",
        label_en="Manufacturer",
        section=1,
        pattern=PATTERNS["manufacturer"],
        prompt_template=(
            "Extract the manufacturer or supplier name from this SDS section.\n"
            "Return ONLY the company name, nothing else.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="cas_number",
        label_pt="Número CAS",
        label_en="CAS Number",
        section=3,
        pattern=PATTERNS["cas_number"],
        prompt_template=(
                "Extract the CAS number (Chemical Abstracts Service number) from this SDS section.\n"
                "CAS numbers have the format: XXXXX-XX-X (2-7 digits, dash, 2 digits, dash, 1 digit).\n\n"
                "Examples: 7664-93-9 (Sulfuric acid), 64-17-5 (Ethanol), 67-56-1 (Methanol).\n\n"
                "Return ONLY the CAS number in correct format (e.g., 1234-56-7).\n"
                "If multiple CAS numbers exist, return the one for the PRIMARY component.\n"
                "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="un_number",
        label_pt="Número ONU",
        label_en="UN Number",
        section=14,
        pattern=PATTERNS["un_number"],
        prompt_template=(
            "Extract the UN number (ONU number) from this SDS section.\n"
            "UN numbers are 4-digit codes like UN1234 or ONU 1234.\n"
            "Return ONLY the 4-digit number, nothing else.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="hazard_class",
        label_pt="Classe de Risco",
        label_en="Hazard Class",
        section=14,
        pattern=PATTERNS["hazard_class"],
        prompt_template=(
            "Extract the UN hazard class from this SDS section.\n"
            "Hazard classes are numbers like 3, 2.1, 6.1, 8, etc.\n"
            "Return ONLY the class number, nothing else.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="packing_group",
        label_pt="Grupo de Embalagem",
        label_en="Packing Group",
        section=14,
        pattern=PATTERNS["packing_group"],
        prompt_template=(
            "Extract the packing group from this SDS section.\n"
            "Packing groups are I, II, or III (Roman numerals).\n"
            "Return ONLY the Roman numeral (I, II, or III), nothing else.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="h_statements",
        label_pt="Frases H",
        label_en="H Statements",
        section=2,
        pattern=PATTERNS["h_statements"],
        required=False,
        prompt_template=(
            "Extract all H-statements (hazard statements) from this SDS section.\n"
            "H-statements have format H followed by 3 digits (e.g., H301, H315).\n"
            "Return all found H-statements separated by commas.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="p_statements",
        label_pt="Frases P",
        label_en="P Statements",
        section=2,
        pattern=PATTERNS["p_statements"],
        required=False,
        prompt_template=(
            "Extract all P-statements (precautionary statements) from this SDS section.\n"
            "P-statements have format P followed by 3 digits (e.g., P280, P302+P352).\n"
            "Return all found P-statements separated by commas.\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="incompatibilities",
        label_pt="Incompatibilidades",
        label_en="Incompatibilities",
        section=10,
        pattern=PATTERNS["incompatibilities"],
        prompt_template=(
            "Extract the incompatible materials from this SDS section.\n"
                "Look for materials that should NOT be mixed or stored with this product.\n"
                "Common keywords: incompatible, avoid contact with, materials to avoid, reacts with.\n\n"
                "Return a comma-separated list of incompatible materials (e.g., 'strong acids, oxidizers, metals').\n"
                "Be specific - use chemical names or classes, not vague terms.\n"
                "If not found or states 'none known', return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
]


# === VALIDATION THRESHOLDS ===
VALIDATION_THRESHOLDS: Final[dict[str, float]] = {
    "valid": 0.9,  # confidence >= 0.9 = valid
    "warning": 0.7,  # confidence 0.7-0.9 = warning
    # confidence < 0.7 = invalid
}


# === UN NUMBER VALID RANGE ===
UN_NUMBER_RANGE: Final[tuple[int, int]] = (4, 3550)  # Valid UN numbers


# === HAZARD CLASSES ===
HAZARD_CLASSES: Final[list[str]] = [
    "1",
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "1.5",
    "1.6",  # Explosives
    "2",
    "2.1",
    "2.2",
    "2.3",  # Gases
    "3",  # Flammable liquids
    "4",
    "4.1",
    "4.2",
    "4.3",  # Flammable solids
    "5",
    "5.1",
    "5.2",  # Oxidizers
    "6",
    "6.1",
    "6.2",  # Toxic
    "7",  # Radioactive
    "8",  # Corrosive
    "9",  # Miscellaneous
]
