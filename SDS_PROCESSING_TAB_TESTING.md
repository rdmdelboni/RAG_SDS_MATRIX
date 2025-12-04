# SDS Processing Tab - Testing Guide

## Overview
The new **🔬 SDS Processing** tab unifies functionality from "SDS (Legacy)" and "Regex Lab (Legacy)" tabs into a single, cohesive interface.

## What's New

### Unified Interface
- **Two modes in one tab**: Switch between Batch Processing and Pattern Testing
- **Seamless workflow**: Test extraction patterns → Apply to batch processing
- **Consistent UI**: Shared settings and controls across modes
- **Legacy tabs preserved**: Both old tabs remain available for comparison

## Features to Test

### 1. Pattern Testing Mode (🔬)

**Purpose**: Test extraction patterns on individual SDS files before batch processing

**How to test**:
1. Open the app and navigate to "🔬 SDS Processing" tab
2. Select "🔬 Pattern Testing" mode (radio button at top)
3. Click "📄 Browse SDS" to select a single PDF file
4. Choose a profile (Auto-detect or specific profile)
5. Optionally filter fields (e.g., `product_name,cas_number`)
6. Toggle "Use RAG" if needed
7. Click "🔍 Extract & Test"
8. Review results in the table with confidence scores:
   - 🟢 Green (≥0.8) = High confidence
   - 🟡 Yellow (0.5-0.8) = Medium confidence
   - 🔴 Red (<0.5) = Low confidence

**Pattern Editor**:
- Expand "Pattern Editor" section (checkbox)
- Edit profile name, field name, regex pattern, and flags
- Click "💾 Save Pattern" to add/update patterns in catalog
- Click "🔄 Reload Profiles" to refresh profile list

**Test Cases**:
- [ ] Load an SDS file and extract all fields
- [ ] Test with specific profile selection
- [ ] Filter by specific fields only
- [ ] Save a new regex pattern
- [ ] Edit existing pattern and reload profiles
- [ ] Check confidence color coding
- [ ] Verify RAG toggle works

### 2. Batch Processing Mode (📁)

**Purpose**: Process multiple SDS files from a folder

**How to test**:
1. Select "📁 Batch Processing" mode
2. Click "📂 Select Folder" to choose a directory with SDS files
3. Review file list:
   - ✓ Green files = Already processed
   - Regular files = Pending processing
4. Configure options:
   - "Use RAG enrichment" - Enable/disable RAG
   - "Include processed files" - Reprocess already processed files
5. Use selection buttons:
   - "Select All" - Check all files
   - "All Pending" - Check only unprocessed files
6. Click "⚙️ Process SDS" to start batch processing
7. Monitor progress bar and status updates
8. Use "⏹️ Stop" to cancel if needed
9. Click "📊 Build Matrix" to create compatibility matrix
10. Click "💾 Export" to save results (Excel/JSON/HTML)

**Test Cases**:
- [ ] Load folder with mixed processed/unprocessed files
- [ ] Select all files and process
- [ ] Select only pending files
- [ ] Toggle "Include processed files" and observe status changes
- [ ] Start processing and monitor progress
- [ ] Stop processing mid-way
- [ ] Build compatibility matrix after processing
- [ ] Export results in different formats

### 3. Seamless Mode Switching

**Purpose**: Transfer settings between modes for efficient workflow

**How to test**:
1. Start in Pattern Testing mode
2. Test extraction on a sample file
3. Click "→ Use in Batch" button
4. Verify:
   - Switches to Batch Processing mode
   - RAG setting copied from test mode
   - If file was selected, its parent folder is auto-loaded
   - File list populated automatically

**Test Cases**:
- [ ] Test pattern → Switch to batch with same folder
- [ ] Verify RAG setting transferred
- [ ] Switch modes multiple times
- [ ] Check that mode state is preserved

## Comparison with Legacy Tabs

### vs "SDS (Legacy)" Tab
| Feature | Legacy | Unified | Status |
|---------|--------|---------|--------|
| Batch processing | ✅ | ✅ | Same |
| Matrix building | ✅ | ✅ | Same |
| Export | ✅ | ✅ | Same |
| Pattern testing | ❌ | ✅ | **New** |
| Mode switching | ❌ | ✅ | **New** |
| Confidence display | ❌ | ✅ | **New** |

### vs "Regex Lab (Legacy)" Tab
| Feature | Legacy | Unified | Status |
|---------|--------|---------|--------|
| Single file testing | ✅ | ✅ | Same |
| Pattern editor | ✅ | ✅ | Same |
| Profile reload | ✅ | ✅ | Same |
| Batch processing | ❌ | ✅ | **New** |
| Mode switching | ❌ | ✅ | **New** |
| Confidence coloring | ❌ | ✅ | **Enhanced** |

## Known Limitations

1. **Batch processing stub**: The `_process_sds_task` method is currently a stub and needs full implementation
2. **No cancel support in test mode**: Pattern testing cannot be cancelled once started
3. **Pattern editor always visible**: Currently not collapsible in initial implementation

## Success Criteria

For the unified tab to replace the legacy tabs, verify:

- [ ] All pattern testing features work correctly
- [ ] All batch processing features work correctly
- [ ] Mode switching is smooth and settings transfer properly
- [ ] No regressions compared to legacy tabs
- [ ] UI is intuitive and responsive
- [ ] Progress feedback is clear in both modes
- [ ] Export and matrix building work as expected
- [ ] Pattern saving/loading functions correctly

## Rollback Plan

If issues are found:
1. Legacy tabs remain available as fallback
2. Report issues in testing
3. Fixes will be applied to unified tab
4. Re-test after fixes
5. Only remove legacy tabs after successful testing period

## Feedback

Please test thoroughly and provide feedback on:
- Usability improvements or issues
- Missing features
- UI/UX suggestions
- Performance concerns
- Any bugs or unexpected behavior

---

**Note**: After successful testing and approval, the legacy tabs will be removed and the unified tab will become the primary SDS processing interface.
