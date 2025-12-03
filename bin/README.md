# Bin Directory

Convenience shell scripts for common operations.

## Available Scripts

### `backup_rag.sh`
Quick backup script for RAG data.

```bash
./bin/backup_rag.sh [output_directory]
```

Example:
```bash
./bin/backup_rag.sh ~/backups/rag-$(date +%Y%m%d)
```

### `process_sds_with_rag.sh`
RAG-enhanced SDS processing for a folder of SDS documents.

```bash
./bin/process_sds_with_rag.sh /path/to/sds [output_file]
```

Examples:
```bash
./bin/process_sds_with_rag.sh /mnt/usb/sds_documents
./bin/process_sds_with_rag.sh ~/Downloads/SDS ~/Desktop/results.json
```

### `run_sds_pipeline.sh`
Run the complete SDS pipeline (extraction + matrix generation).

```bash
./bin/run_sds_pipeline.sh /path/to/sds [output_dir]
```

Examples:
```bash
./bin/run_sds_pipeline.sh /mnt/usb/sds
./bin/run_sds_pipeline.sh ~/Downloads/SDS ~/Desktop/Results
```

## Requirements

- Virtual environment must be created at `.venv/`
- All Python dependencies installed (`pip install -r requirements.txt`)
- Ollama running (for LLM features)

## See Also

- `/scripts/` - Python utility scripts
- `/guides/` - Detailed feature guides
