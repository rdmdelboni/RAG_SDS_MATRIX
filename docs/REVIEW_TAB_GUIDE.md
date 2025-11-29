# PDF Review Tab - User Guide

## Overview

The **Review Tab** is a powerful feature that allows you to review, validate, and correct extracted data from processed PDF documents. This feedback loop helps improve the RAG (Retrieval-Augmented Generation) system's accuracy over time.

## Features

### 1. **Browse Processed Documents**
- View all processed PDFs in an organized table
- See key extracted information at a glance:
  - Filename
  - Processing status (Success ✅, Partial ⚠️, Failed ❌)
  - Product name
  - CAS number
  - UN number
  - Hazard class
  - Average confidence score

### 2. **Filter and Search**
- **Status Filter**: View documents by processing status
  - All: Show all documents
  - Success: Only successfully processed documents
  - Partial: Partially extracted documents
  - Failed: Documents that failed processing

- **Limit Control**: Set how many documents to display (default: 50)

### 3. **Edit Extracted Data**
To edit a document's extracted data:
1. **Double-click** on any row in the table
2. An edit dialog will open showing all extraction fields

### 4. **Edit Dialog**

The edit dialog displays all extracted fields with:

#### Editable Fields:
- Product Name
- Manufacturer
- CAS Number
- UN Number
- Hazard Class
- Packing Group
- H Statements (Hazard statements)
- P Statements (Precautionary statements)
- Incompatibilities

#### Field Information:
Each field shows:
- **Current value**: The extracted or previously corrected value
- **Source**: How the data was extracted (e.g., `heuristic`, `rag`, `user_correction`)
- **Context**: Text snippet where the information was found in the original document
- **Confidence**: Score indicating extraction quality (0.0 to 1.0)

### 5. **Making Corrections**

To correct data:
1. Edit the field value directly in the input box
2. Long fields (H statements, P statements, incompatibilities) have multi-line text areas
3. Adjust confidence if needed (user corrections default to 1.0)
4. Click **💾 Save Changes** to save

### 6. **View Original Document**

While editing, you can:
- Click **📄 View Original** to open the source PDF file
- This helps verify information and make accurate corrections

### 7. **Impact on RAG System**

When you save corrections:
- Fields are marked with `source: user_correction`
- Validation status is set to `validated`
- Confidence is set to your specified value (default: 1.0)
- The RAG system will prioritize corrected data in future extractions
- This creates a positive feedback loop, improving accuracy over time

## Usage Workflow

### Typical Review Workflow:

1. **Process PDFs**: Use the SDS tab to process your PDF documents
2. **Navigate to Review Tab**: Click on the "Review" tab
3. **Filter as needed**: Set status filter and limit
4. **Click Refresh**: Load the latest data
5. **Review entries**: Look for low confidence scores or partial statuses
6. **Double-click to edit**: Open documents that need correction
7. **Make corrections**: Update incorrect or missing information
8. **Save changes**: Click save to update the database

### Best Practices:

- **Prioritize low confidence**: Focus on documents with confidence < 70%
- **Verify critical fields**: Always verify CAS numbers, UN numbers, and hazard classes
- **Use context clues**: Read the context snippet to understand where data came from
- **Check originals**: When in doubt, open the original PDF
- **Batch review**: Process similar documents together for consistency

## Data Fields Explained

| Field | Description | Example |
|-------|-------------|---------|
| **Product Name** | Commercial or chemical name of the product | "Sodium Hydroxide Solution 50%" |
| **Manufacturer** | Company that manufactures or supplies | "ACME Chemicals LTDA" |
| **CAS Number** | Chemical Abstracts Service registry number | "1310-73-2" |
| **UN Number** | United Nations dangerous goods number | "1824" |
| **Hazard Class** | UN hazard classification | "8" (Corrosive) |
| **Packing Group** | UN packing group (I, II, III) | "II" |
| **H Statements** | Hazard statements (comma-separated) | "H290, H314, H335" |
| **P Statements** | Precautionary statements | "P280, P305+P351+P338" |
| **Incompatibilities** | Materials to avoid contact with | "Strong acids, aluminum, zinc" |

## Keyboard Shortcuts

- **Double-click row**: Open edit dialog
- **ESC** (in dialog): Cancel without saving
- **Enter** (in single-line fields): Move to next field

## Troubleshooting

### "No data found"
- Ensure you have processed some PDF documents first
- Check the status filter - try setting it to "All"
- Increase the limit value

### "Error loading data"
- Check the database connection
- Verify DuckDB is accessible
- Check application logs for details

### Edit dialog won't open
- Ensure the document ID is valid
- Try refreshing the data
- Check application logs

### Changes not saving
- Verify database write permissions
- Check for field validation errors
- Review application logs for error messages

## Integration with Other Features

### RAG Knowledge Base
Corrected data improves:
- Future document processing accuracy
- Search and retrieval quality
- Chemical compatibility analysis

### Matrix Building
Validated data ensures:
- More accurate incompatibility matrices
- Better hazard classifications
- Higher quality safety reports

### Quality Dashboard
Review tab corrections are tracked in:
- Quality metrics
- Confidence score improvements
- Validation status reports

## Technical Details

### Database Updates
- Uses `store_extraction()` method
- Updates existing extractions or creates new ones
- Maintains full audit trail with timestamps
- Preserves original extraction context

### Data Flow
1. User makes correction → 
2. `_on_save_edits()` called → 
3. `_save_edits_async()` processes in background → 
4. `db.store_extraction()` updates database → 
5. Table refreshes with new data

### Source Tracking
Corrections are marked as:
```python
source = "user_correction"
validation_status = "validated"
context = "User corrected via review tab"
confidence = 1.0  # or user-specified
```

## Future Enhancements

Planned improvements:
- Bulk editing capabilities
- Export corrections for training data
- Comparison view (original vs. corrected)
- Suggestion system based on similar documents
- Annotation tools for ambiguous extractions
- History tracking for all corrections

## Support

For issues or questions:
- Check the main README.md
- Review application logs in `data/logs/`
- Check database integrity with Status tab

---

**Version**: 1.0.0  
**Last Updated**: November 2025
