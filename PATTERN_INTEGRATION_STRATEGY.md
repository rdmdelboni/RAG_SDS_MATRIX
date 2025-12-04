# Pattern Integration Strategy: Single Test → Batch Processing

## Overview

This document explains how to integrate regex patterns between **Single SDS Test** mode and **Batch Processing** mode, creating a unified pattern management system.

## Current Architecture

### Single SDS Test Mode (formerly Pattern Testing)
- Tests extraction on a **single SDS file**
- Uses `ProfileRouter` to select regex profiles
- Allows **editing and saving** new patterns via Pattern Editor
- Patterns saved to `data/regex/` directory as JSON files
- Results show confidence scores with color coding

### Batch Processing Mode
- Processes **multiple SDS files** from a folder
- Currently uses basic extraction (needs enhancement)
- Should leverage **all available regex profiles**
- Should apply **heuristics** to select best profile per file

## Integration Goals

1. **Shared Pattern Catalog**: Both modes use the same regex patterns
2. **Profile Auto-Selection**: Batch mode applies smart heuristics to choose best profile
3. **Pattern Evolution**: New patterns created in Single Test mode automatically available for Batch mode
4. **Confidence-Based Routing**: Use confidence scores to validate profile selection

---

## Implementation Strategy

### Phase 1: Unified Pattern Management ✅ (Already Implemented)

Both modes already share:
- `RegexCatalog` (`src/sds/regex_catalog.py`) - Central pattern repository
- `ProfileRouter` (`src/sds/profile_router.py`) - Profile selection logic
- Pattern storage in `data/regex/*.json`

**How it works:**
```python
# Single Test Mode saves a new pattern
catalog = get_regex_catalog()
catalog.add_pattern(profile_name, field_name, pattern, flags)

# Batch Mode immediately sees the new pattern
router = ProfileRouter(catalog)
router.route(text)  # Uses all available patterns including new ones
```

### Phase 2: Enhanced Batch Processing (TO IMPLEMENT)

Currently, the `_process_sds_task` method in batch mode is a **stub**. Here's how to enhance it:

#### Step 1: Profile Auto-Detection

```python
def _process_single_sds(self, file_path: Path, use_rag: bool) -> dict:
    """Process a single SDS file using profile auto-detection."""
    from ...sds.extractor import SDSExtractor
    from ...sds.profile_router import ProfileRouter
    
    extractor = SDSExtractor()
    router = ProfileRouter(self.context.regex_catalog)
    
    # Step 1: Auto-detect best profile
    with open(file_path, 'rb') as f:
        text_content = extract_text_from_pdf(f)
    
    # Route to best profile based on content
    detected_profile = router.route(text_content)
    
    # Step 2: Extract using detected profile
    result = extractor.extract(
        file_path=file_path,
        profile_name=detected_profile,
        use_rag=use_rag
    )
    
    return {
        'file': file_path.name,
        'profile_used': detected_profile,
        'extracted_data': result.data,
        'confidence_scores': result.confidence,
        'timestamp': datetime.now().isoformat()
    }
```

#### Step 2: Apply Heuristics for Profile Selection

The `ProfileRouter` already implements heuristics:

```python
# In src/sds/profile_router.py
class ProfileRouter:
    def route(self, text: str) -> str:
        """Auto-detect best profile using multiple heuristics."""
        
        # Heuristic 1: Check for manufacturer signatures
        if "sigma-aldrich" in text.lower():
            return "sigma_aldrich"
        elif "fisher scientific" in text.lower():
            return "fisher_scientific"
        
        # Heuristic 2: Check for format patterns
        if self._has_tabular_structure(text):
            return "tabular_profile"
        
        # Heuristic 3: Try all profiles and use highest confidence
        best_profile = "default"
        best_score = 0.0
        
        for profile_name in self.list_profiles():
            test_result = self._test_profile(text, profile_name)
            avg_confidence = sum(test_result.confidence.values()) / len(test_result.confidence)
            
            if avg_confidence > best_score:
                best_score = avg_confidence
                best_profile = profile_name
        
        return best_profile
```

**Enhance these heuristics by:**

1. **Manufacturer Detection** (high priority)
   - Parse company name from SDS header
   - Maintain mapping: `{"Sigma-Aldrich": "sigma_aldrich_profile"}`
   
2. **Document Structure Analysis**
   - Detect tabular vs prose formats
   - Identify section numbering schemes (GHS, OSHA, etc.)
   
3. **Confidence-Based Validation**
   - Try multiple profiles
   - Choose profile with highest average confidence
   - Fallback to "default" if all scores < 0.5

4. **Caching for Performance**
   - Cache profile decisions per manufacturer
   - Skip re-detection for same vendor

#### Step 3: Implement Full Batch Processing Loop

```python
def _process_sds_task(self, files: list[Path], use_rag: bool) -> None:
    """Process multiple SDS files with progress tracking."""
    total = len(files)
    results = []
    
    for i, file_path in enumerate(files):
        # Check if cancelled
        if not self._processing:
            self.signals.progress.emit(100, "Processing cancelled")
            break
        
        # Update progress
        progress_pct = int((i / total) * 100)
        self.signals.progress.emit(
            progress_pct,
            f"Processing {file_path.name} ({i+1}/{total})..."
        )
        
        try:
            # Process single file with auto-detection
            result = self._process_single_sds(file_path, use_rag)
            results.append(result)
            
            # Emit intermediate result
            self.signals.data.emit({
                'type': 'sds_processed',
                'file': file_path.name,
                'data': result
            })
            
        except Exception as e:
            self.signals.error.emit(f"Error processing {file_path.name}: {e}")
            results.append({
                'file': file_path.name,
                'error': str(e),
                'profile_used': 'none'
            })
    
    # Final results
    self.signals.progress.emit(100, f"Completed {len(results)} files")
    self.signals.finished.emit({'results': results, 'total': total})
```

### Phase 3: Pattern Learning & Feedback Loop

Enable the system to **learn** from user corrections:

#### Scenario: User Creates Pattern in Single Test Mode

1. User tests an SDS file
2. Sees low confidence score (e.g., 0.4 for `product_name`)
3. Opens Pattern Editor
4. Creates better regex pattern
5. Saves pattern → **automatically added to catalog**

```python
# In Pattern Editor save handler
def _on_save_pattern(self):
    profile = self.profile_input.text()
    field = self.field_input.text()
    pattern = self.pattern_input.text()
    flags = self.flags_input.text()
    
    # Save to catalog
    catalog = get_regex_catalog()
    catalog.add_pattern(profile, field, pattern, flags)
    
    # Immediately available for batch processing!
    self._set_status(f"✅ Pattern saved to '{profile}' profile")
    self._refresh_profiles()
```

#### Scenario: Batch Processing Uses New Pattern

Next time batch processing runs:

```python
# ProfileRouter automatically loads ALL patterns from catalog
router = ProfileRouter(catalog)  # Includes newly saved patterns

# When routing this manufacturer again:
profile = router.route(text)  # May now select the improved profile!
```

### Phase 4: Confidence-Based Quality Control

Add validation to batch processing:

```python
def _process_single_sds(self, file_path: Path, use_rag: bool) -> dict:
    result = extractor.extract(file_path, profile_name, use_rag)
    
    # Calculate average confidence
    avg_confidence = sum(result.confidence.values()) / len(result.confidence)
    
    # Flag low-quality extractions
    quality_status = "✅ High" if avg_confidence >= 0.8 else \
                     "⚠️ Medium" if avg_confidence >= 0.5 else \
                     "❌ Low"
    
    return {
        'file': file_path.name,
        'profile_used': profile_name,
        'extracted_data': result.data,
        'confidence_scores': result.confidence,
        'avg_confidence': avg_confidence,
        'quality_status': quality_status,
        'needs_review': avg_confidence < 0.5  # Flag for manual review
    }
```

Display in batch results table:

| File | Profile | Quality | Avg Confidence | Actions |
|------|---------|---------|----------------|---------|
| sds1.pdf | sigma_aldrich | ✅ High | 0.92 | View |
| sds2.pdf | fisher | ⚠️ Medium | 0.67 | Review |
| sds3.pdf | generic | ❌ Low | 0.34 | **Edit Patterns** |

Clicking "Edit Patterns" on a low-confidence result:
1. Switches to **Single SDS Test** mode
2. Loads the problematic file
3. Shows extraction results
4. Opens Pattern Editor
5. User improves patterns
6. Returns to Batch mode with improved patterns!

---

## Workflow: Pattern Creation → Batch Integration

### Example End-to-End Workflow

**Day 1: Discover New Manufacturer**

1. User receives SDS from "NewChem Corp"
2. Switches to **Single SDS Test** mode
3. Loads `newchem_sds.pdf`
4. Selects "Auto-detect" profile
5. System uses "default" profile (no NewChem profile exists)
6. Results show mixed confidence: 
   - ✅ `product_name`: 0.85
   - ❌ `cas_number`: 0.22 (poorly formatted)
   - ⚠️ `hazards`: 0.61

**Day 1: Create Custom Patterns**

7. User opens **Pattern Editor**
8. Creates new profile: `newchem_corp`
9. Adds custom pattern for `cas_number`:
   ```regex
   CAS[\s-]*Number:?\s*(\d{2,7}-\d{2}-\d)
   ```
10. Clicks **💾 Save Pattern**
11. Re-tests extraction → now `cas_number`: 0.91 ✅

**Day 2: Batch Process with New Profile**

12. User switches to **Batch Processing** mode
13. Selects folder with 50 NewChem SDS files
14. Clicks **⚙️ Process SDS**
15. System auto-detects "NewChem Corp" in each file
16. **Automatically uses the `newchem_corp` profile** created yesterday!
17. All 50 files extracted with high confidence

---

## Technical Implementation Details

### File Structure

```
data/regex/
├── default.json           # Fallback patterns
├── sigma_aldrich.json     # Sigma-Aldrich specific
├── fisher_scientific.json # Fisher Scientific specific
├── newchem_corp.json      # User-created profile ← NEW!
└── ...

src/sds/
├── regex_catalog.py       # Central pattern repository
├── profile_router.py      # Auto-detection logic
├── extractor.py           # Extraction engine
└── confidence.py          # Confidence scoring
```

### Pattern File Format

```json
{
  "profile_name": "newchem_corp",
  "manufacturer": "NewChem Corporation",
  "patterns": {
    "product_name": {
      "regex": "Product:\\s*(.+?)(?:\\n|$)",
      "flags": "IGNORECASE",
      "confidence_weight": 1.0
    },
    "cas_number": {
      "regex": "CAS[\\s-]*Number:?\\s*(\\d{2,7}-\\d{2}-\\d)",
      "flags": "IGNORECASE",
      "confidence_weight": 1.2
    }
  },
  "heuristics": {
    "manufacturer_keywords": ["newchem", "newchem corp"],
    "header_signature": "SAFETY DATA SHEET.*NewChem",
    "section_format": "numeric"
  }
}
```

### Heuristic Matching Logic

```python
class ProfileRouter:
    def route(self, text: str) -> str:
        # 1. Check manufacturer keywords
        for profile in self.catalog.profiles:
            keywords = profile.get('heuristics', {}).get('manufacturer_keywords', [])
            if any(kw.lower() in text.lower() for kw in keywords):
                return profile['profile_name']
        
        # 2. Check header signatures
        for profile in self.catalog.profiles:
            signature = profile.get('heuristics', {}).get('header_signature')
            if signature and re.search(signature, text, re.IGNORECASE):
                return profile['profile_name']
        
        # 3. Try all profiles, pick highest confidence
        return self._confidence_based_routing(text)
```

---

## Benefits of This Approach

### ✅ Unified Pattern Management
- Single source of truth: `RegexCatalog`
- Patterns created anywhere, available everywhere
- No manual sync between test and batch modes

### ✅ Continuous Improvement
- Users refine patterns as they encounter edge cases
- Each improvement benefits future batch processing
- System gets smarter over time

### ✅ Confidence-Driven Quality
- Automatic flagging of low-confidence extractions
- Easy path to improvement via Pattern Editor
- Quality metrics visible throughout workflow

### ✅ Manufacturer-Specific Optimization
- Dedicated profiles for each vendor
- Heuristics enable automatic profile selection
- Handles manufacturer-specific formats elegantly

### ✅ Minimal Code Changes
- Most infrastructure already exists
- Main work: Implement `_process_sds_task` properly
- Enhance `ProfileRouter` heuristics

---

## Implementation Checklist

### Phase 1: Core Integration ✅
- [x] Shared `RegexCatalog` between modes
- [x] Pattern Editor saves to central catalog
- [x] Profile reload functionality

### Phase 2: Batch Processing Enhancement
- [ ] Implement `_process_single_sds()` method
- [ ] Add profile auto-detection per file
- [ ] Implement full `_process_sds_task()` loop
- [ ] Add progress tracking throughout batch process
- [ ] Display profile used in results table

### Phase 3: Heuristics Enhancement
- [ ] Add manufacturer keyword detection
- [ ] Add header signature matching
- [ ] Implement confidence-based fallback
- [ ] Add caching for repeated manufacturers
- [ ] Test with 10+ different SDS formats

### Phase 4: Quality Control
- [ ] Calculate and display average confidence per file
- [ ] Add quality status indicators (✅/⚠️/❌)
- [ ] Flag low-confidence results for review
- [ ] Add "Edit Patterns" action to results table
- [ ] Implement seamless jump to Single Test mode

### Phase 5: Pattern Learning
- [ ] Track which patterns were most effective
- [ ] Suggest pattern improvements based on low-confidence fields
- [ ] Add pattern versioning/history
- [ ] Export/import pattern profiles for sharing

---

## Future Enhancements

### Machine Learning Integration
- Train ML model on confidence scores
- Predict best profile before extraction
- Learn from user corrections

### Pattern Library Sharing
- Community-contributed profiles
- Download profiles for common manufacturers
- Rate and review patterns

### Visual Pattern Builder
- GUI for constructing regex patterns
- Live preview with test data
- Validation and testing tools

### Batch Re-Processing
- Re-run batch with improved patterns
- Compare before/after results
- Selective re-processing of low-confidence files

---

## Summary

The integration is **mostly complete** at the architecture level:
1. Both modes share `RegexCatalog` ✅
2. Pattern Editor saves to central location ✅
3. ProfileRouter provides auto-detection ✅

**What needs implementation:**
1. Full batch processing loop in `_process_sds_task()`
2. Enhanced heuristics in `ProfileRouter.route()`
3. Quality control and review workflow
4. UI enhancements for displaying profile selection

The key insight: **Patterns flow naturally from Single Test → Catalog → Batch Processing** without manual intervention. Creating a pattern in test mode immediately makes it available for batch processing through the shared catalog.
