# Enhanced SDS Extraction Fields

## Current Fields (14)
✓ product_name, manufacturer, cas_number, un_number, hazard_class, packing_group
✓ h_statements, p_statements, incompatibilities
✓ molecular_formula, molecular_weight, iupac_name, inchi_key
✓ _document_confidence

## Proposed Additional Fields (20+ new fields)

### Section 1: Identification
- [x] product_name (existing)
- [x] manufacturer (existing) 
- [ ] **supplier_phone** - Emergency contact
- [ ] **supplier_email** - Contact email
- [ ] **supplier_address** - Physical address
- [ ] **emergency_phone** - 24hr emergency number
- [ ] **product_code** - Internal catalog/SKU
- [ ] **synonyms** - Alternative chemical names

### Section 2: Hazard Identification
- [x] h_statements (existing)
- [x] p_statements (existing)
- [ ] **ghs_pictograms** - GHS symbol codes (GHS01, GHS02, etc.)
- [ ] **signal_word** - "Danger" or "Warning"
- [ ] **hazard_statements_text** - Full text descriptions
- [ ] **precautionary_statements_text** - Full precaution text

### Section 3: Composition
- [x] cas_number (existing)
- [x] molecular_formula (existing)
- [x] molecular_weight (existing)
- [x] iupac_name (existing)
- [x] inchi_key (existing)
- [ ] **concentration** - % composition (e.g., "95-100%")
- [ ] **impurities** - Known contaminants
- [ ] **additives** - Stabilizers, preservatives

### Section 4: First Aid
- [ ] **first_aid_inhalation** - Inhalation response
- [ ] **first_aid_skin** - Skin contact response
- [ ] **first_aid_eye** - Eye contact response
- [ ] **first_aid_ingestion** - Ingestion response
- [ ] **symptoms** - Acute/delayed symptoms

### Section 5: Fire Fighting
- [ ] **flammability** - Flammable/Non-flammable
- [ ] **flash_point** - Flash point temperature (°C)
- [ ] **autoignition_temp** - Autoignition temperature
- [ ] **flammable_limits** - LEL/UEL percentages
- [ ] **extinguishing_media** - Suitable extinguishers
- [ ] **fire_hazards** - Special fire hazards

### Section 7: Handling & Storage
- [ ] **handling_precautions** - Safe handling practices
- [ ] **storage_conditions** - Temperature, humidity, etc.
- [ ] **storage_incompatibilities** - Storage separation requirements
- [x] incompatibilities (existing - Section 10)

### Section 8: Exposure Controls
- [ ] **exposure_limit_osha_pel** - OSHA Permissible Exposure Limit
- [ ] **exposure_limit_acgih_tlv** - ACGIH Threshold Limit Value
- [ ] **exposure_limit_niosh_rel** - NIOSH Recommended Exposure Limit
- [ ] **exposure_limit_idlh** - Immediately Dangerous to Life/Health
- [ ] **ppe_respiratory** - Respiratory protection required
- [ ] **ppe_hand** - Hand protection (glove type)
- [ ] **ppe_eye** - Eye protection
- [ ] **ppe_body** - Body protection
- [ ] **engineering_controls** - Ventilation requirements

### Section 9: Physical Properties
- [ ] **physical_state** - Solid/Liquid/Gas
- [ ] **color** - Color description
- [ ] **odor** - Odor description
- [ ] **ph** - pH value
- [ ] **melting_point** - Melting point (°C)
- [ ] **boiling_point** - Boiling point (°C)
- [ ] **vapor_pressure** - Vapor pressure
- [ ] **vapor_density** - Vapor density
- [ ] **specific_gravity** - Specific gravity/density
- [ ] **solubility** - Water solubility
- [ ] **viscosity** - Viscosity value

### Section 10: Stability & Reactivity
- [x] incompatibilities (existing)
- [ ] **stability** - Stable/Unstable conditions
- [ ] **conditions_to_avoid** - Temperature, pressure, etc.
- [ ] **hazardous_polymerization** - Will/Will not occur
- [ ] **hazardous_decomposition** - Decomposition products

### Section 11: Toxicological Information
- [ ] **toxicity_oral_ld50** - Oral LD50 value
- [ ] **toxicity_dermal_ld50** - Dermal LD50 value
- [ ] **toxicity_inhalation_lc50** - Inhalation LC50 value
- [ ] **routes_of_exposure** - Inhalation/skin/eye/ingestion
- [ ] **carcinogenicity** - IARC/NTP/OSHA classification
- [ ] **mutagenicity** - Mutagenic effects
- [ ] **reproductive_toxicity** - Reproductive effects

### Section 12: Ecological Information
- [ ] **ecotoxicity_aquatic** - Aquatic toxicity data
- [ ] **persistence_degradability** - Biodegradability
- [ ] **bioaccumulation** - Bioconcentration factor
- [ ] **environmental_fate** - Environmental persistence

### Section 14: Transport Information
- [x] un_number (existing)
- [x] hazard_class (existing)
- [x] packing_group (existing)
- [ ] **proper_shipping_name** - Official transport name
- [ ] **marine_pollutant** - Yes/No
- [ ] **dot_classification** - DOT specific classification
- [ ] **imdg_code** - Marine transport code
- [ ] **iata_code** - Air transport code

### Section 15: Regulatory Information
- [ ] **sara_311_312** - SARA hazard categories
- [ ] **sara_313** - Toxic chemical listing
- [ ] **tsca_status** - TSCA inventory status
- [ ] **cercla_rq** - Reportable quantity
- [ ] **california_prop65** - Prop 65 warning

### Section 16: Other Information
- [ ] **sds_date** - SDS preparation/revision date
- [ ] **sds_version** - Version number
- [ ] **nfpa_rating** - NFPA 704 diamond (Health/Fire/Reactivity)
- [ ] **hmis_rating** - HMIS rating

## Extraction Priority Levels

### Priority 1 (High Value for Knowledge Graph)
- exposure limits (OSHA PEL, ACGIH TLV, NIOSH REL, IDLH)
- physical properties (flash_point, boiling_point, ph)
- toxicity data (LD50 values, carcinogenicity)
- regulatory info (TSCA, SARA, Prop 65)
- proper_shipping_name
- ghs_pictograms, signal_word

### Priority 2 (Enrichment Data)
- first aid measures
- PPE requirements
- storage conditions
- fire fighting measures
- physical state, color, odor
- concentration
- sds_date, sds_version

### Priority 3 (Nice to Have)
- synonyms
- contact information
- ecological data
- NFPA/HMIS ratings

## Implementation Strategy

1. **Update constants.py** - Add new FieldDefinition entries
2. **Update regex patterns** - Add patterns for structured fields
3. **Enhance LLM prompts** - Add detailed extraction prompts
4. **Database migration** - No schema change needed (extractions table is flexible)
5. **Re-run extraction** - Process existing PDFs with enhanced fields
6. **Update UI** - Display new fields in records tab

## Benefits

- **Better chemical matching** - Synonyms help identify same chemicals
- **Safety intelligence** - Exposure limits enable risk assessment
- **Regulatory compliance** - SARA/TSCA/Prop65 tracking
- **Physical properties** - Enable similarity by properties
- **Toxicity comparison** - LD50 values for risk ranking
- **Complete safety profile** - First aid, PPE, handling instructions
