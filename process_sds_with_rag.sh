#!/bin/bash
# RAG-Enhanced SDS Processing
# Process SDS files using all RAG knowledge

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

if [ -z "$1" ]; then
    echo "❌ Uso: ./process_sds_with_rag.sh /caminho/para/sds [output_file]"
    echo ""
    echo "Exemplo:"
    echo "  ./process_sds_with_rag.sh /mnt/usb/sds_documents"
    echo "  ./process_sds_with_rag.sh ~/Downloads/SDS ~/Desktop/results.json"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_FILE="${2:-.}"

if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ Pasta não existe: $INPUT_DIR"
    exit 1
fi

# Activate venv
source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || {
    echo "❌ Virtual environment not found"
    exit 1
}

echo "🔄 Iniciando processamento SDS com RAG"
echo "📁 Entrada: $INPUT_DIR"
if [ "$OUTPUT_FILE" != "." ]; then
    echo "📁 Saída: $OUTPUT_FILE"
fi
echo ""

# Run processor
if [ "$OUTPUT_FILE" = "." ]; then
    python "$PROJECT_ROOT/scripts/rag_sds_processor.py" \
        --input "$INPUT_DIR"
else
    python "$PROJECT_ROOT/scripts/rag_sds_processor.py" \
        --input "$INPUT_DIR" \
        --output "$OUTPUT_FILE"
fi

echo ""
echo "✅ Processamento concluído!"
