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
    # === PRIORITY 1 ADDITIONS: High-value fields for knowledge graph ===
    # Section 2: GHS Classification
    FieldDefinition(
        name="ghs_pictograms",
        label_pt="Pictogramas GHS",
        label_en="GHS Pictograms",
        section=2,
        pattern=re.compile(
            r"(GHS0[1-9](?:[,;\s]+GHS0[1-9])*)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract all GHS pictogram codes from this SDS section.\n"
            "GHS codes are: GHS01 (exploding bomb), GHS02 (flame), GHS03 (flame over circle), "
            "GHS04 (gas cylinder), GHS05 (corrosion), GHS06 (skull), GHS07 (exclamation), "
            "GHS08 (health hazard), GHS09 (environment).\n"
            "Return all found codes separated by commas (e.g., 'GHS02, GHS07').\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="signal_word",
        label_pt="Palavra de Advertência",
        label_en="Signal Word",
        section=2,
        pattern=re.compile(
            r"\b(DANGER|WARNING|PERIGO|ATENÇÃO)\b",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the GHS signal word from this SDS section.\n"
            "Signal words are either 'DANGER' (more severe) or 'WARNING' (less severe).\n"
            "In Portuguese: 'PERIGO' or 'ATENÇÃO'.\n"
            "Return ONLY the signal word found (DANGER, WARNING, PERIGO, or ATENÇÃO).\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    # Section 8: Exposure Limits
    FieldDefinition(
        name="exposure_limit_osha_pel",
        label_pt="Limite OSHA PEL",
        label_en="OSHA PEL",
        section=8,
        pattern=re.compile(
            r"(?:OSHA|PEL)\s*[:\-]?\s*([\d.]+\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the OSHA PEL (Permissible Exposure Limit) from this SDS section.\n"
            "PEL is usually expressed in ppm or mg/m³.\n"
            "Examples: '10 ppm', '5 mg/m³', '200 ppm TWA'.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_acgih_tlv",
        label_pt="Limite ACGIH TLV",
        label_en="ACGIH TLV",
        section=8,
        pattern=re.compile(
            r"(?:ACGIH|TLV)\s*[:\-]?\s*([\d.]+\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the ACGIH TLV (Threshold Limit Value) from this SDS section.\n"
            "TLV is usually expressed in ppm or mg/m³.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_niosh_rel",
        label_pt="Limite NIOSH REL",
        label_en="NIOSH REL",
        section=8,
        pattern=re.compile(
            r"(?:NIOSH|REL)\s*[:\-]?\s*([\d.]+\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the NIOSH REL (Recommended Exposure Limit) from this SDS section.\n"
            "REL is usually expressed in ppm or mg/m³.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_idlh",
        label_pt="Limite IDLH",
        label_en="IDLH",
        section=8,
        pattern=re.compile(
            r"IDLH\s*[:\-]?\s*([\d.]+\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the IDLH (Immediately Dangerous to Life or Health) value from this SDS section.\n"
            "IDLH is usually expressed in ppm or mg/m³.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    # Section 9: Physical Properties
    FieldDefinition(
        name="flash_point",
        label_pt="Ponto de Fulgor",
        label_en="Flash Point",
        section=9,
        pattern=re.compile(
            r"(?:flash\s*point|ponto\s*de\s*fulgor|ponto\s*de\s*inflamação)\s*[:\-]?\s*([\-]?[\d.]+\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the flash point from this SDS section.\n"
            "Flash point is the lowest temperature at which vapors ignite.\n"
            "Usually expressed as a temperature in °C or °F.\n"
            "Examples: '23°C', '-18°F', 'Closed cup: 60°C'.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="boiling_point",
        label_pt="Ponto de Ebulição",
        label_en="Boiling Point",
        section=9,
        pattern=re.compile(
            r"(?:boiling\s*point|ponto\s*de\s*ebulição)\s*[:\-]?\s*([\-]?[\d.]+\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the boiling point from this SDS section.\n"
            "Return the temperature with units (°C or °F).\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="melting_point",
        label_pt="Ponto de Fusão",
        label_en="Melting Point",
        section=9,
        pattern=re.compile(
            r"(?:melting\s*point|freezing\s*point|ponto\s*de\s*fusão|ponto\s*de\s*congelamento)\s*[:\-]?\s*([\-]?[\d.]+\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the melting point or freezing point from this SDS section.\n"
            "Return the temperature with units (°C or °F).\n"
            "If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="ph",
        label_pt="pH",
        label_en="pH",
        section=9,
        pattern=re.compile(
            r"\bpH\s*[:\-]?\s*([\d.]+(?:\s*[-~]\s*[\d.]+)?)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the pH value from this SDS section.\n"
            "pH is a measure of acidity/alkalinity from 0-14.\n"
            "Examples: '7.0', '2.5', '11-13', 'pH 8'.\n"
            "Return just the numeric value or range. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="physical_state",
        label_pt="Estado Físico",
        label_en="Physical State",
        section=9,
        pattern=re.compile(
            r"(?:physical\s*state|estado\s*físico|form)\s*[:\-]?\s*(solid|liquid|gas|sólido|líquido|gasoso|powder|pó)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the physical state from this SDS section.\n"
            "Physical state is: Solid, Liquid, Gas, or forms like Powder, Paste, etc.\n"
            "Return the state in English. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    # Section 11: Toxicity
    FieldDefinition(
        name="toxicity_oral_ld50",
        label_pt="LD50 Oral",
        label_en="Oral LD50",
        section=11,
        pattern=re.compile(
            r"(?:oral|ingestão).*?LD50\s*[:\-]?\s*([\d,]+\s*mg/kg)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the oral LD50 value from this SDS section.\n"
            "LD50 is the lethal dose that kills 50% of test subjects.\n"
            "Usually expressed as mg/kg body weight.\n"
            "Examples: '500 mg/kg', '2,500 mg/kg (rat)'.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="toxicity_dermal_ld50",
        label_pt="LD50 Dérmico",
        label_en="Dermal LD50",
        section=11,
        pattern=re.compile(
            r"(?:dermal|dérmica|cutânea).*?LD50\s*[:\-]?\s*([\d,]+\s*mg/kg)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the dermal LD50 value from this SDS section.\n"
            "Dermal LD50 is for skin absorption, expressed as mg/kg body weight.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="toxicity_inhalation_lc50",
        label_pt="LC50 Inalação",
        label_en="Inhalation LC50",
        section=11,
        pattern=re.compile(
            r"(?:inhalation|inalação).*?LC50\s*[:\-]?\s*([\d,]+\s*(?:ppm|mg/[Ll]|mg/m[³3]))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the inhalation LC50 value from this SDS section.\n"
            "LC50 is the lethal concentration for inhalation, usually ppm or mg/L or mg/m³.\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    # Section 14: Transport
    FieldDefinition(
        name="proper_shipping_name",
        label_pt="Nome Apropriado de Transporte",
        label_en="Proper Shipping Name",
        section=14,
        pattern=None,  # Too complex for regex
        required=False,
        prompt_template=(
            "Extract the Proper Shipping Name (PSN) from this SDS section.\n"
            "This is the official name used for transport, often near the UN number.\n"
            "Examples: 'SULFURIC ACID', 'ETHANOL SOLUTION', 'CORROSIVE LIQUID, N.O.S.'.\n"
            "Return the exact shipping name. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    # Section 15: Regulatory
    FieldDefinition(
        name="tsca_status",
        label_pt="Status TSCA",
        label_en="TSCA Status",
        section=15,
        pattern=re.compile(
            r"TSCA\s*[:\-]?\s*(listed|not listed|exempt|yes|no|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the TSCA (Toxic Substances Control Act) status from this SDS section.\n"
            "TSCA indicates if chemical is listed on US EPA inventory.\n"
            "Common values: 'Listed', 'Not listed', 'Exempt', 'Yes', 'No'.\n"
            "Return the status. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="sara_313",
        label_pt="SARA 313",
        label_en="SARA 313",
        section=15,
        pattern=re.compile(
            r"SARA\s*313\s*[:\-]?\s*(yes|no|listed|not listed|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the SARA 313 status from this SDS section.\n"
            "SARA 313 lists toxic chemicals requiring reporting.\n"
            "Return Yes/No or Listed/Not Listed. If not found, return 'NOT_FOUND'.\n\n"
            "Text:\n{text}"
        ),
    ),
    FieldDefinition(
        name="california_prop65",
        label_pt="California Prop 65",
        label_en="California Prop 65",
        section=15,
        pattern=re.compile(
            r"(?:Prop(?:osition)?\s*65|California.*?65)\s*[:\-]?\s*(yes|no|listed|not listed|warning|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the California Proposition 65 status from this SDS section.\n"
            "Prop 65 lists chemicals known to cause cancer or reproductive harm in California.\n"
            "Return Yes/No/Listed/Warning. If not found, return 'NOT_FOUND'.\n\n"
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
