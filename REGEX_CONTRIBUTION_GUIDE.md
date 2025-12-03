# Regex Profile Contribution Guide

## Overview

The RAG_SDS_MATRIX system uses regex profiles to extract structured data from manufacturer-specific SDS formats. Community contributions help improve extraction accuracy across different manufacturers.

## What Are Regex Profiles?

Regex profiles define extraction patterns for specific SDS layouts:

```python
{
    "manufacturer": "Example Chemical Co.",
    "priority": 50,  # 0-100, higher = preferred match
    "patterns": {
        "product_name": r"Product\s*Name:\s*([^\n]+)",
        "cas_number": r"CAS\s*No\.:\s*(\d{1,7}-\d{2}-\d)",
        "composition": r"Component.*?CAS.*?%.*?(?=\n\n|\Z)"
    },
    "validation": {
        "required_fields": ["product_name", "cas_number"],
        "test_cases": [...]
    }
}
```

## Current Built-in Profiles

1. **Sigma-Aldrich** - Priority 90
2. **Fisher Scientific** - Priority 85  
3. **VWR** - Priority 80

All stored in: `data/regex/profiles/`

## How to Contribute a Profile

### Step 1: Collect Sample SDS Files

- Gather 3-5 SDS files from target manufacturer
- Ensure variety (different products, formats)
- Save as PDFs in: `data/regex/samples/{manufacturer}/`

### Step 2: Extract Text

```bash
python scripts/extract_sds_text.py \
    --input data/regex/samples/YourManufacturer/ \
    --output data/regex/extracted/YourManufacturer/
```

This converts PDFs to clean text for pattern testing.

### Step 3: Create Profile JSON

Use the template: `data/regex/profiles/_TEMPLATE.json`

```json
{
    "manufacturer": "YourManufacturer",
    "priority": 50,
    "description": "Profile for YourManufacturer SDS format (2024)",
    "version": "1.0",
    "patterns": {
        "product_name": "YOUR_REGEX_HERE",
        "product_code": "YOUR_REGEX_HERE",
        "cas_number": "YOUR_REGEX_HERE",
        "composition_table": "YOUR_REGEX_HERE",
        "hazard_statements": "YOUR_REGEX_HERE",
        "precautionary_statements": "YOUR_REGEX_HERE",
        "physical_properties": "YOUR_REGEX_HERE",
        "first_aid": "YOUR_REGEX_HERE"
    },
    "composition_parsing": {
        "row_pattern": "YOUR_ROW_REGEX",
        "name_group": 1,
        "cas_group": 2,
        "concentration_group": 3
    },
    "validation": {
        "required_fields": ["product_name", "cas_number"],
        "test_cases": [
            {
                "file": "sample1.txt",
                "expected": {
                    "product_name": "Expected Product Name",
                    "cas_number": "123-45-6"
                }
            }
        ]
    }
}
```

### Step 4: Test Your Profile

```bash
python scripts/validate_regex_profile.py \
    --profile data/regex/profiles/yourmanufacturer.json \
    --samples data/regex/extracted/YourManufacturer/
```

This runs validation tests and reports:
- ✅ Fields successfully extracted
- ❌ Missing required fields
- ⚠️ Low confidence extractions

### Step 5: Refine Patterns

Common issues and solutions:

**Problem: Pattern too strict**
```regex
❌ Product Name: (.+)  # Only matches if colon present
✅ Product\s*(?:Name)?:?\s*(.+?)(?=\n|$)  # Flexible
```

**Problem: Greedy matching**
```regex
❌ Component.*CAS.*?(.+)  # Captures too much
✅ Component[^\n]*CAS[^\n]*?(\d+-\d+-\d)  # Stops at CAS
```

**Problem: Whitespace variations**
```regex
❌ CAS No.: (\d+)  # Requires exact spacing
✅ CAS\s*(?:No\.?|Number)?:?\s*(\d{1,7}-\d{2}-\d)  # Handles variations
```

### Step 6: Submit via GitHub

1. Fork the repository
2. Add your profile: `data/regex/profiles/yourmanufacturer.json`
3. Add test samples (optional): `data/regex/samples/YourManufacturer/`
4. Create pull request with:
   - Profile JSON
   - Validation test results
   - Brief description of SDS format

## Profile Quality Criteria

### Required ✅

- [ ] Valid JSON syntax
- [ ] All required fields in schema
- [ ] At least 2 test cases with expected output
- [ ] Patterns extract correct data from test samples
- [ ] No catastrophic backtracking (regex performance)

### Recommended ⭐

- [ ] Priority set appropriately (50-70 for new profiles)
- [ ] Composition table parsing with row patterns
- [ ] Handles common variations (spacing, punctuation)
- [ ] Description includes format year/version
- [ ] Comments explaining complex patterns

### Bonus 🎯

- [ ] Multiple format versions (e.g., 2020 vs 2024 layouts)
- [ ] Fallback patterns for partial matches
- [ ] Non-English variants (if applicable)
- [ ] Performance benchmarks included

## Regex Pattern Library

### Common Components

**CAS Number:**
```regex
\b\d{1,7}-\d{2}-\d\b
```

**Product Code:**
```regex
(?:Cat\.?\s*#?|Catalog|Product\s+Code):?\s*([A-Z0-9-]+)
```

**Concentration Range:**
```regex
(?:(\d+(?:\.\d+)?)\s*-\s*)?(\d+(?:\.\d+)?)\s*%
```

**Hazard Statement:**
```regex
H\d{3}[A-Z]*(?:\s*\+\s*H\d{3}[A-Z]*)*
```

**Precautionary Statement:**
```regex
P\d{3}(?:\s*\+\s*P\d{3})*
```

### Section Extraction

**Multiline Sections:**
```regex
Section\s+(\d+)[:\.]?\s*([^\n]+)\n(.*?)(?=\nSection\s+\d+|$)
```

**Table Rows:**
```regex
(?m)^([^|\t\n]+)[\t|]+([^|\t\n]+)[\t|]+([^|\t\n]+)$
```

## Testing Tools

### Interactive Tester

```bash
python scripts/test_regex_interactive.py
```

Opens TUI for:
- Load sample SDS text
- Test patterns live
- See matched groups
- Adjust patterns in real-time

### Batch Validator

```bash
python scripts/validate_all_profiles.py
```

Tests all profiles against all samples, generates report:
```
Sigma-Aldrich: 98% success (49/50 samples)
Fisher: 95% success (38/40 samples)
YourManufacturer: 85% success (17/20 samples)  ⚠️ Needs improvement
```

### Performance Analyzer

```bash
python scripts/benchmark_regex.py --profile yourmanufacturer.json
```

Checks for:
- Catastrophic backtracking
- Slow patterns (>100ms)
- Memory usage

## Common Pitfalls

### 1. Over-specific Patterns

❌ **Bad:**
```regex
Product Name: (.+)  # Only works if exact format
```

✅ **Good:**
```regex
(?i)product\s*(?:name)?:?\s*(.+?)(?=\n|$)  # Case-insensitive, flexible
```

### 2. Greedy Quantifiers

❌ **Bad:**
```regex
Component.*?CAS.*?(.+)  # Captures everything to end
```

✅ **Good:**
```regex
Component[^\n]*?CAS[^\n]*?(\d+-\d+-\d)  # Stops at CAS
```

### 3. Missing Anchors

❌ **Bad:**
```regex
\d+-\d+-\d  # Matches partial CAS numbers
```

✅ **Good:**
```regex
\b\d{1,7}-\d{2}-\d\b  # Word boundaries
```

### 4. Not Handling Variations

❌ **Bad:**
```regex
CAS No.: (\d+)  # Fails on "CAS Number", "CAS#"
```

✅ **Good:**
```regex
CAS\s*(?:No\.?|Number|#)?:?\s*(\d{1,7}-\d{2}-\d)
```

## FAQ

**Q: What priority should I use?**  
A: Start with 50. Increase to 60-70 if profile is very accurate and widely used.

**Q: My regex works in testing but fails in production?**  
A: Check PDF extraction quality. Sometimes text extraction introduces artifacts.

**Q: Can I have multiple profiles for one manufacturer?**  
A: Yes! Use different priorities for different format versions.

**Q: How do I handle non-English SDS?**  
A: Create separate profiles with appropriate Unicode patterns.

**Q: What if patterns overlap with existing profiles?**  
A: Higher priority profile takes precedence. Test thoroughly.

## Support

- **Documentation:** `docs/REGEX_LAB.md`
- **Issues:** GitHub Issues with label `regex-profile`
- **Examples:** Check `data/regex/profiles/*.json`
- **Community:** GitHub Discussions

## License

By contributing, you agree to license your profile under the same license as the project (MIT).

---

**Thank you for improving SDS extraction accuracy! 🎯**
