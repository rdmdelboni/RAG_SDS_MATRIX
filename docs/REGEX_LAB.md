# Regex Lab / Profile System

This repo now supports a vendor regex catalog to cut LLM usage for known SDS layouts and a small CLI helper to test patterns.

## Catalog location
- Default path: `data/regex/regexes.json` (override with `REGEX_CATALOG_PATH` env).
- Format:
```json
{
  "version": "2024-10",
  "profiles": [
    {
      "name": "Sigma-Aldrich",
      "identifiers": ["SIGMA-ALDRICH", "MERCK"],
      "regexes": {
        "product_name": {"pattern": "Product name\\s*:\\s*(.+?)(?:\\n|$)", "flags": "im"},
        "cas_number":   {"pattern": "CAS-No\\.\\s*:\\s*(\\d{2,7}-\\d{2}-\\d)", "flags": "im"}
      },
      "notes": "Optional free text",
      "version": "2024-10"
    }
  ]
}
```
- `flags` supports `i` (ignore case), `m` (multiline), `s` (dotall), `x` (verbose).
- Profiles from the catalog are merged over built-ins; names are case-insensitive.

## Using the Regex Lab CLI
```
python scripts/regex_lab.py --file path/to/sds.pdf           # auto-detect profile
python scripts/regex_lab.py --file path/to/sds.pdf --profile "Sigma-Aldrich"
python scripts/regex_lab.py --file path/to/sds.pdf --fields cas_number product_name
python scripts/regex_lab.py --list-profiles
```
The script prints matches, confidence, and a short context snippet so you can quickly tune patterns.

## How extraction uses profiles
- `ProfileRouter` loads the catalog and picks a profile by identifiers in the header text (first ~3000 chars) or by `--profile` in the CLI.
- `HeuristicExtractor` applies the profile’s regex overrides before the generic patterns, tagging results with `source=heuristic_profile_<name>` and high confidence.
- If no profile matches, the generic heuristics run as before and the LLM pass is used when confidence is low.

## Workflow to add/tune a vendor
1. Add or update an entry in `data/regex/regexes.json`.
2. Run the CLI against a few SDS PDFs to validate matches.
3. Commit the catalog change once fields you care about (product_name, cas_number, hazard_class, etc.) are covered with high confidence.
4. In UI/processing, LLM usage will drop automatically for those vendors because heuristics now hit with higher confidence.
