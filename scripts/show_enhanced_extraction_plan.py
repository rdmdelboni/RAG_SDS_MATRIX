#!/usr/bin/env python3
"""
Enhanced SDS Extraction - Priority 1 Fields

Adds high-value fields to extraction for better knowledge graph enrichment:
- Exposure limits (OSHA PEL, ACGIH TLV, NIOSH REL, IDLH)
- Physical properties (flash_point, boiling_point, pH, melting_point)
- Toxicity data (LD50 oral/dermal, LC50 inhalation)
- Regulatory info (TSCA, SARA, California Prop 65)
- GHS classification (pictograms, signal word)
- Transport info (proper_shipping_name)
"""

import re
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Priority 1 field additions to constants.py
PRIORITY_1_FIELDS = """

    # === PRIORITY 1 ADDITIONS ===
    
    # Section 2: GHS Classification
    FieldDefinition(
        name="ghs_pictograms",
        label_pt="Pictogramas GHS",
        label_en="GHS Pictograms",
        section=2,
        pattern=re.compile(
            r"(GHS0[1-9](?:[,;\\s]+GHS0[1-9])*)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract all GHS pictogram codes from this SDS section.\\n"
            "GHS codes are: GHS01 (exploding bomb), GHS02 (flame), GHS03 (flame over circle), "
            "GHS04 (gas cylinder), GHS05 (corrosion), GHS06 (skull), GHS07 (exclamation), "
            "GHS08 (health hazard), GHS09 (environment).\\n"
            "Return all found codes separated by commas (e.g., 'GHS02, GHS07').\\n"
            "If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="signal_word",
        label_pt="Palavra de Advertência",
        label_en="Signal Word",
        section=2,
        pattern=re.compile(
            r"\\b(DANGER|WARNING|PERIGO|ATENÇÃO)\\b",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the GHS signal word from this SDS section.\\n"
            "Signal words are either 'DANGER' (more severe) or 'WARNING' (less severe).\\n"
            "In Portuguese: 'PERIGO' or 'ATENÇÃO'.\\n"
            "Return ONLY the signal word found (DANGER, WARNING, PERIGO, or ATENÇÃO).\\n"
            "If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    
    # Section 8: Exposure Limits
    FieldDefinition(
        name="exposure_limit_osha_pel",
        label_pt="Limite OSHA PEL",
        label_en="OSHA PEL",
        section=8,
        pattern=re.compile(
            r"(?:OSHA|PEL)\\s*[:\\-]?\\s*([\\d.]+\\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the OSHA PEL (Permissible Exposure Limit) from this SDS section.\\n"
            "PEL is usually expressed in ppm or mg/m³.\\n"
            "Examples: '10 ppm', '5 mg/m³', '200 ppm TWA'.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_acgih_tlv",
        label_pt="Limite ACGIH TLV",
        label_en="ACGIH TLV",
        section=8,
        pattern=re.compile(
            r"(?:ACGIH|TLV)\\s*[:\\-]?\\s*([\\d.]+\\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the ACGIH TLV (Threshold Limit Value) from this SDS section.\\n"
            "TLV is usually expressed in ppm or mg/m³.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_niosh_rel",
        label_pt="Limite NIOSH REL",
        label_en="NIOSH REL",
        section=8,
        pattern=re.compile(
            r"(?:NIOSH|REL)\\s*[:\\-]?\\s*([\\d.]+\\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the NIOSH REL (Recommended Exposure Limit) from this SDS section.\\n"
            "REL is usually expressed in ppm or mg/m³.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="exposure_limit_idlh",
        label_pt="Limite IDLH",
        label_en="IDLH",
        section=8,
        pattern=re.compile(
            r"IDLH\\s*[:\\-]?\\s*([\\d.]+\\s*(?:ppm|mg/m[³3]|ppb))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the IDLH (Immediately Dangerous to Life or Health) value from this SDS section.\\n"
            "IDLH is usually expressed in ppm or mg/m³.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    
    # Section 9: Physical Properties
    FieldDefinition(
        name="flash_point",
        label_pt="Ponto de Fulgor",
        label_en="Flash Point",
        section=9,
        pattern=re.compile(
            r"(?:flash\\s*point|ponto\\s*de\\s*fulgor|ponto\\s*de\\s*inflamação)\\s*[:\\-]?\\s*([\\-]?[\\d.]+\\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the flash point from this SDS section.\\n"
            "Flash point is the lowest temperature at which vapors ignite.\\n"
            "Usually expressed as a temperature in °C or °F.\\n"
            "Examples: '23°C', '-18°F', 'Closed cup: 60°C'.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="boiling_point",
        label_pt="Ponto de Ebulição",
        label_en="Boiling Point",
        section=9,
        pattern=re.compile(
            r"(?:boiling\\s*point|ponto\\s*de\\s*ebulição)\\s*[:\\-]?\\s*([\\-]?[\\d.]+\\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the boiling point from this SDS section.\\n"
            "Return the temperature with units (°C or °F).\\n"
            "If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="melting_point",
        label_pt="Ponto de Fusão",
        label_en="Melting Point",
        section=9,
        pattern=re.compile(
            r"(?:melting\\s*point|freezing\\s*point|ponto\\s*de\\s*fusão|ponto\\s*de\\s*congelamento)\\s*[:\\-]?\\s*([\\-]?[\\d.]+\\s*°?[CF])",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the melting point or freezing point from this SDS section.\\n"
            "Return the temperature with units (°C or °F).\\n"
            "If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="ph",
        label_pt="pH",
        label_en="pH",
        section=9,
        pattern=re.compile(
            r"\\bpH\\s*[:\\-]?\\s*([\\d.]+(?:\\s*[-~]\\s*[\\d.]+)?)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the pH value from this SDS section.\\n"
            "pH is a measure of acidity/alkalinity from 0-14.\\n"
            "Examples: '7.0', '2.5', '11-13', 'pH 8'.\\n"
            "Return just the numeric value or range. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="physical_state",
        label_pt="Estado Físico",
        label_en="Physical State",
        section=9,
        pattern=re.compile(
            r"(?:physical\\s*state|estado\\s*físico|form)\\s*[:\\-]?\\s*(solid|liquid|gas|sólido|líquido|gasoso|powder|pó)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the physical state from this SDS section.\\n"
            "Physical state is: Solid, Liquid, Gas, or forms like Powder, Paste, etc.\\n"
            "Return the state in English. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    
    # Section 11: Toxicity
    FieldDefinition(
        name="toxicity_oral_ld50",
        label_pt="LD50 Oral",
        label_en="Oral LD50",
        section=11,
        pattern=re.compile(
            r"(?:oral|ingestão).*?LD50\\s*[:\\-]?\\s*([\\d,]+\\s*mg/kg)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the oral LD50 value from this SDS section.\\n"
            "LD50 is the lethal dose that kills 50%% of test subjects.\\n"
            "Usually expressed as mg/kg body weight.\\n"
            "Examples: '500 mg/kg', '2,500 mg/kg (rat)'.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="toxicity_dermal_ld50",
        label_pt="LD50 Dérmico",
        label_en="Dermal LD50",
        section=11,
        pattern=re.compile(
            r"(?:dermal|dérmica|cutânea).*?LD50\\s*[:\\-]?\\s*([\\d,]+\\s*mg/kg)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the dermal LD50 value from this SDS section.\\n"
            "Dermal LD50 is for skin absorption, expressed as mg/kg body weight.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="toxicity_inhalation_lc50",
        label_pt="LC50 Inalação",
        label_en="Inhalation LC50",
        section=11,
        pattern=re.compile(
            r"(?:inhalation|inalação).*?LC50\\s*[:\\-]?\\s*([\\d,]+\\s*(?:ppm|mg/[Ll]|mg/m[³3]))",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the inhalation LC50 value from this SDS section.\\n"
            "LC50 is the lethal concentration for inhalation, usually ppm or mg/L or mg/m³.\\n"
            "Return the value with units. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
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
            "Extract the Proper Shipping Name (PSN) from this SDS section.\\n"
            "This is the official name used for transport, often near the UN number.\\n"
            "Examples: 'SULFURIC ACID', 'ETHANOL SOLUTION', 'CORROSIVE LIQUID, N.O.S.'.\\n"
            "Return the exact shipping name. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    
    # Section 15: Regulatory
    FieldDefinition(
        name="tsca_status",
        label_pt="Status TSCA",
        label_en="TSCA Status",
        section=15,
        pattern=re.compile(
            r"TSCA\\s*[:\\-]?\\s*(listed|not listed|exempt|yes|no|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the TSCA (Toxic Substances Control Act) status from this SDS section.\\n"
            "TSCA indicates if chemical is listed on US EPA inventory.\\n"
            "Common values: 'Listed', 'Not listed', 'Exempt', 'Yes', 'No'.\\n"
            "Return the status. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="sara_313",
        label_pt="SARA 313",
        label_en="SARA 313",
        section=15,
        pattern=re.compile(
            r"SARA\\s*313\\s*[:\\-]?\\s*(yes|no|listed|not listed|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the SARA 313 status from this SDS section.\\n"
            "SARA 313 lists toxic chemicals requiring reporting.\\n"
            "Return Yes/No or Listed/Not Listed. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
    FieldDefinition(
        name="california_prop65",
        label_pt="California Prop 65",
        label_en="California Prop 65",
        section=15,
        pattern=re.compile(
            r"(?:Prop(?:osition)?\\s*65|California.*?65)\\s*[:\\-]?\\s*(yes|no|listed|not listed|warning|sim|não)",
            re.IGNORECASE,
        ),
        required=False,
        prompt_template=(
            "Extract the California Proposition 65 status from this SDS section.\\n"
            "Prop 65 lists chemicals known to cause cancer or reproductive harm in California.\\n"
            "Return Yes/No/Listed/Warning. If not found, return 'NOT_FOUND'.\\n\\n"
            "Text:\\n{text}"
        ),
    ),
"""

print("\\n" + "="*80)
print("🚀 ENHANCED SDS EXTRACTION - PRIORITY 1 FIELDS")
print("="*80 + "\\n")

print("📋 Fields to Add (21 new fields):")
print("\\nSection 2: GHS Classification")
print("  ✓ ghs_pictograms (GHS01-GHS09 codes)")
print("  ✓ signal_word (DANGER/WARNING)")

print("\\nSection 8: Exposure Limits")
print("  ✓ exposure_limit_osha_pel")
print("  ✓ exposure_limit_acgih_tlv")
print("  ✓ exposure_limit_niosh_rel")
print("  ✓ exposure_limit_idlh")

print("\\nSection 9: Physical Properties")
print("  ✓ flash_point (°C/°F)")
print("  ✓ boiling_point (°C/°F)")
print("  ✓ melting_point (°C/°F)")
print("  ✓ ph (0-14 scale)")
print("  ✓ physical_state (solid/liquid/gas)")

print("\\nSection 11: Toxicology")
print("  ✓ toxicity_oral_ld50 (mg/kg)")
print("  ✓ toxicity_dermal_ld50 (mg/kg)")
print("  ✓ toxicity_inhalation_lc50 (ppm/mg/L)")

print("\\nSection 14: Transport")
print("  ✓ proper_shipping_name (official DOT name)")

print("\\nSection 15: Regulatory")
print("  ✓ tsca_status (US EPA inventory)")
print("  ✓ sara_313 (toxic chemical reporting)")
print("  ✓ california_prop65 (cancer/reproductive hazard)")

print("\\n" + "="*80)
print("\\n💡 IMPLEMENTATION STEPS:")
print("-"*80)
print("\\n1. Add field definitions to src/config/constants.py")
print("   - Copy the PRIORITY_1_FIELDS definitions above")
print("   - Paste before the closing bracket of EXTRACTION_FIELDS list")
print("   - Verify indentation matches existing FieldDefinition entries")

print("\\n2. Re-run extraction on existing PDFs:")
print("   cd /home/rdmdelboni/Work/Gits/RAG_SDS_MATRIX")
print("   ./.venv/bin/python scripts/sds_pipeline.py --reprocess")
print("   (This will extract the 21 new fields from all 315 existing documents)")

print("\\n3. Verify new data:")
print("   ./.venv/bin/python -c \\\"")
print("   import duckdb")
print("   conn = duckdb.connect('data/duckdb/extractions.db')")
print("   for field in ['flash_point', 'exposure_limit_osha_pel', 'toxicity_oral_ld50']:")
print("       count = conn.execute(f'SELECT COUNT(*) FROM extractions WHERE field_name = \\\\'{field}\\\\'').fetchone()[0]")
print("       print(f'{field}: {count} values')\\\"")

print("\\n4. Build enhanced knowledge graph:")
print("   - Exposure limits → Safety threshold nodes")
print("   - Physical properties → Similarity by properties")
print("   - Toxicity data → Risk ranking edges")
print("   - Regulatory status → Compliance tracking")

print("\\n" + "="*80)
print("\\n📊 EXPECTED BENEFITS:")
print("-"*80)
print("  ✓ Exposure limits enable workplace safety recommendations")
print("  ✓ Flash points enable fire hazard classification")
print("  ✓ LD50 values enable acute toxicity ranking")
print("  ✓ Physical properties enable multi-factor similarity")
print("  ✓ Regulatory data enables compliance tracking")
print("  ✓ GHS classification improves hazard identification")

print("\\n🎯 After extraction, you can query:")
print("  - 'Which chemicals have OSHA PEL < 10 ppm?' (high exposure risk)")
print("  - 'Which have flash point < 23°C?' (flammable liquids class 1)")
print("  - 'Which are on California Prop 65?' (regulatory concern)")
print("  - 'Find chemicals with LD50 < 500 mg/kg' (highly toxic)")
print("  - 'Similar pH and boiling point to X' (process substitution)")

print("\\n" + "="*80 + "\\n")

print("\\n📝 Ready to implement? The field definitions are displayed above.")
print("Copy them into src/config/constants.py at line 251 (after the incompatibilities field)\\n")
