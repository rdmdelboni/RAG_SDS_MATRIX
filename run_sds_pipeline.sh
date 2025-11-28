#!/bin/bash
# Quick SDS Pipeline Script
# Usage: ./run_sds_pipeline.sh /caminho/para/sds [/caminho/output]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

if [ -z "$1" ]; then
    echo "❌ Use: ./run_sds_pipeline.sh /caminho/para/sds [output_dir]"
    echo ""
    echo "Exemplos:"
    echo "  ./run_sds_pipeline.sh /mnt/usb/sds"
    echo "  ./run_sds_pipeline.sh ~/Downloads/SDS ~/Desktop/Results"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="${2:-.}"

if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ Pasta não existe: $INPUT_DIR"
    exit 1
fi

# Activate venv
source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || {
    echo "❌ Virtual environment not found"
    exit 1
}

echo "🔄 Iniciando SDS Pipeline"
echo "📁 Entrada: $INPUT_DIR"
echo "📁 Saída: $OUTPUT_DIR"
echo ""

# Run pipeline
python "$PROJECT_ROOT/scripts/sds_pipeline.py" \
    --input "$INPUT_DIR" \
    --output "$OUTPUT_DIR"

echo ""
echo "✅ Pipeline concluído!"
echo "📊 Verifique os resultados em: $OUTPUT_DIR"
