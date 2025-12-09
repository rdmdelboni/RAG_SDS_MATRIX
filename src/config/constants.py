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
              "Extract the PRIMARY CHEMICAL product name from this SDS section.\n\n"
              "Step 1: Look for sections labeled 'Product name', 'Chemical name', 'Product identifier', or 'Identificação do produto'.\n"
              "Step 2: Identify the CHEMICAL NAME (e.g., 'Sulfuric acid') vs brand/trade names (e.g., 'ACME H2SO4').\n"
              "Step 3: If a percentage concentration is present (e.g., '98%'), REMOVE it from the chemical name.\n"
              "Step 4: Ignore catalog numbers, batch codes, and product codes (e.g., 'H2SO4-98', 'Batch #123').\n"
              "Step 5: If multiple names are present, return the PRIMARY chemical name (usually listed first).\n\n"
              "Examples:\n"
              "- Input: 'Product name: Ácido Sulfúrico 98% (Batch H2SO4-001)'\n"
              "  Output: 'Ácido Sulfúrico'\n"
              "- Input: 'Chemical name: Ethanol (96% solution, IUPAC name: ethan-1-ol)'\n"
              "  Output: 'Ethanol'\n"
              "- Input: 'ACME Brand H2SO4 98%'\n"
              "  Output: 'Sulfuric acid' (or Ácido Sulfúrico)\n\n"
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
                "Extract the CAS number (Chemical Abstracts Service number) from this SDS section.\n\n"
                "Step 1: Look for 'CAS', 'CAS number', 'CAS #', or 'Número CAS' in the text.\n"
                "Step 2: CAS numbers have EXACT format: 2-7 digits, dash, 2 digits, dash, 1 digit (e.g., 7664-93-9).\n"
                "Step 3: The format pattern is: ##### -##-# OR ####### -##-#\n"
                "Step 4: If multiple CAS numbers are listed, return ONLY the PRIMARY one (usually listed first, often for the main chemical).\n"
                "Step 5: Verify the CAS number is not inside parentheses with 'approx', 'circa', or 'similar to'.\n\n"
                "Format validation:\n"
                "- CORRECT: 7664-93-9, 64-17-5, 67-56-1, 123456-78-9\n"
                "- INCORRECT: 98%, 2024-01-15, H2SO4, Section 1.2\n\n"
                "Examples:\n"
                "- Input: 'CAS number: 7664-93-9 (Sulfuric acid 98%)'\n"
                "  Output: 7664-93-9\n"
                "- Input: '64-17-5 (Ethanol), 7732-18-5 (Water)'\n"
                "  Output: 64-17-5 (primary component)\n\n"
                "Return ONLY the CAS number in correct format (e.g., 1234-56-7).\n"
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
            "Extract the UN number (ONU number) from this SDS section.\n\n"
            "Step 1: Look for 'UN', 'U.N.', 'ONU', or 'Número ONU' in the text.\n"
            "Step 2: UN numbers are ALWAYS 4-digit codes in formats:\n"
            "   - UN1234, UN 1234, UN#1234\n"
            "   - ONU1234, ONU 1234\n"
            "Step 3: The 4 digits should be NUMERIC only (0-9), no letters.\n"
            "Step 4: UN numbers typically range from 1001 to 3480.\n"
            "Step 5: Ignore dates, phone numbers, or section numbers that look like 4 digits.\n\n"
            "Valid examples:\n"
            "- 'UN1198' or 'UN 1198' (Hydrazine)\n"
            "- 'ONU2030' or 'ONU 2030' (Hydrazine aqueous solution)\n"
            "- Section 14 UN/ID: 1008\n\n"
            "Invalid examples:\n"
            "- '2024' (year), '1234-5678' (phone), 'UN1A23' (contains letters)\n\n"
            "Return ONLY the 4-digit number (e.g., 1198), nothing else.\n"
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
            "Extract the UN hazard class from this SDS section.\n\n"
            "Step 1: Look for 'Hazard class', 'Classe de risco', 'UN class', or 'Classe' in transport/classification section.\n"
            "Step 2: UN hazard classes are:\n"
            "   Single digit: 1, 2, 3, 4, 5, 6, 7, 8, 9\n"
            "   With decimal: 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2, 4.3, 5.1, 5.2, 6.1, 6.2\n"
            "Step 3: Class meanings:\n"
            "   - 1: Explosives, 2: Gases, 3: Flammable liquids, 4: Flammable solids\n"
            "   - 5: Oxidizers, 6: Toxic/Infectious, 7: Radioactive, 8: Corrosive, 9: Miscellaneous\n"
            "Step 4: If multiple classes listed, return the PRIMARY class (usually first one listed).\n"
            "Step 5: Do NOT include 'Class' or 'Classe' in the output, only the number/decimal.\n\n"
            "Valid examples:\n"
            "- '3' (Flammable liquid)\n"
            "- '2.1' (Flammable gas)\n"
            "- '6.1' (Toxic substance)\n"
            "- 'Hazard Class: 8' → Output: '8'\n\n"
            "Invalid examples:\n"
            "- 'Class 3.5' (3.5 is not valid), '3a' (letters), 'Section 3'\n\n"
            "Return ONLY the hazard class number (e.g., 3, 2.1, 8).\n"
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
            "Extract the packing group from this SDS section.\n\n"
            "Step 1: Look for 'Packing group', 'Grupo de embalagem', 'PG', or 'P.G.' in the text.\n"
            "Step 2: Packing groups are ALWAYS one of exactly three options:\n"
            "   - I (Roman numeral 1): HIGH danger - most restrictive, highest hazard\n"
            "   - II (Roman numeral 2): MEDIUM danger - moderate hazard\n"
            "   - III (Roman numeral 3): LOW danger - least restrictive, lower hazard\n"
            "Step 3: Packing group is determined by the hazard level of the substance.\n"
            "Step 4: Accept formats: I, II, III (uppercase) or i, ii, iii (lowercase).\n"
            "Step 5: Normalize output to UPPERCASE Roman numerals.\n\n"
            "Valid examples:\n"
            "- 'Packing Group: I' → Output: 'I'\n"
            "- 'PG II' → Output: 'II'\n"
            "- 'Grupo de embalagem III' → Output: 'III'\n"
            "- 'P.G.: ii' → Output: 'II'\n\n"
            "Invalid examples:\n"
            "- 'I (first section)' (context dependent), 'Packing IV' (IV doesn't exist), 'PG 1' (use numerals not digits)\n\n"
            "Return ONLY the Roman numeral (I, II, or III) in UPPERCASE.\n"
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
            "Extract all H-statements (hazard statements) from this SDS section.\n\n"
            "Step 1: Look for 'H-statements', 'Hazard statements', 'H phrases', or 'Frases H'.\n"
            "Step 2: H-statements ALWAYS have format: 'H' followed by EXACTLY 3 digits (e.g., H301, H315, H225).\n"
            "Step 3: Multiple H-statements can be combined with '+' (e.g., H301+H311).\n"
            "Step 4: Find ALL H-statements in the section, not just the first one.\n"
            "Step 5: Return them in the order they appear, separated by commas.\n"
            "Step 6: Remove duplicate H-statements (e.g., if H301 appears twice, list it once).\n\n"
            "Valid H-statements range:\n"
            "- Physical hazards: H200-H229, H240-H290\n"
            "- Health hazards: H300-H373\n"
            "- Environmental hazards: H400-H413\n\n"
            "Examples:\n"
            "- Input: 'Hazard statements: H225 (Highly flammable liquid), H302 (Harmful if swallowed)'\n"
            "  Output: 'H225, H302'\n"
            "- Input: 'H315 + H319 cause eye irritation'\n"
            "  Output: 'H315+H319'\n"
            "- Input: 'No H-statements listed'\n"
            "  Output: 'NOT_FOUND'\n\n"
            "Return all H-statements found, separated by commas (maintain + for combined statements).\n"
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
            "Extract all P-statements (precautionary statements) from this SDS section.\n\n"
            "Step 1: Look for 'P-statements', 'Precautionary statements', 'P phrases', or 'Frases P'.\n"
            "Step 2: P-statements ALWAYS have format: 'P' followed by EXACTLY 3 digits (e.g., P280, P302+P352).\n"
            "Step 3: Multiple P-statements can be combined with '+' (e.g., P302+P352, P261+P271).\n"
            "Step 4: Find ALL P-statements in the section.\n"
            "Step 5: Return them in the order they appear, separated by commas.\n"
            "Step 6: Keep '+' connectors for combined statements, but separate different groups by commas.\n"
            "Step 7: Remove duplicates (if P280 appears twice, list once).\n\n"
            "Valid P-statement ranges:\n"
            "- Prevention: P100-P199\n"
            "- Response: P200-P299\n"
            "- Storage: P300-P399\n"
            "- Disposal: P400-P499\n\n"
            "Examples:\n"
            "- Input: 'P-statements: P280 (Wear protective equipment), P302+P352 (IF ON SKIN: Wash)'\n"
            "  Output: 'P280, P302+P352'\n"
            "- Input: 'P261, P271, P304+P340 Inhalation hazard'\n"
            "  Output: 'P261, P271, P304+P340'\n"
            "- Input: 'No precautionary statements'\n"
            "  Output: 'NOT_FOUND'\n\n"
            "Return all P-statements found, separated by commas (maintain + for combined statements).\n"
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
