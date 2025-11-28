#!/bin/bash
# Quick backup script for RAG data
# Usage: ./backup_rag.sh [output_directory]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default output directory
OUTPUT_DIR="${1:-.}"

# Activate venv
source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || {
    echo "❌ Virtual environment not found"
    exit 1
}

# Run backup
echo "📦 Iniciando backup da RAG..."
python "$SCRIPT_DIR/rag_backup.py" --output "$OUTPUT_DIR"

echo ""
echo "✅ Backup concluído com sucesso!"
echo "📁 Verifique a pasta: $OUTPUT_DIR"
