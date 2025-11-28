#!/usr/bin/env bash
# Helper script to exercise knowledge ingestion without using the UI.
# - Loads .env
# - Optionally runs crawl4ai with default seeds (polite settings in .env)
# - Ingests crawl4ai output (if any), a few free URLs, and a sample Google search

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
else
  echo ".env not found at $ENV_FILE. Create it first (copy .env.example)." >&2
  exit 1
fi

python - <<'PY' >/dev/null 2>&1
from importlib.util import find_spec
missing = []
for mod in ("requests", "trafilatura", "bs4"):
    if find_spec(mod) is None:
        missing.append(mod)
if missing:
    raise SystemExit(f"Missing Python packages: {', '.join(missing)}. Install via pip.")
PY

ingest_snapshot() {
  local snapshot_path="$1"
  python - <<'PY'
from pathlib import Path
from src.rag.ingestion_service import KnowledgeIngestionService

snapshot = Path(r"${snapshot_path}")
service = KnowledgeIngestionService()
summary = service.ingest_snapshot_file(snapshot)
print(summary.to_message())
PY
}

ingest_simple_urls() {
  python - <<'PY'
from src.rag.ingestion_service import KnowledgeIngestionService

urls = [
    "https://www.osha.gov/",
    "https://www.cdc.gov/niosh/",
    "https://sistemasinter.cetesb.sp.gov.br/produtos/produto_consulta_completa.asp",
    "https://cameochemicals.noaa.gov/help/reactivity/reactive_groups.htm",
    "https://safescience.cas.org/",
    "https://www.cdc.gov/niosh/npg/npgdcas.html",
]
service = KnowledgeIngestionService()
summary = service.ingest_simple_urls(urls)
print(summary.to_message())
PY
}

ingest_google_search() {
  python - <<'PY'
from src.rag.ingestion_service import KnowledgeIngestionService

service = KnowledgeIngestionService()
summary = service.ingest_web_search("flammable liquid storage best practices", max_results=3)
print(summary.to_message())
PY
}

run_crawl4ai() {
  if [[ -z "${CRAW4AI_COMMAND:-}" ]]; then
    echo "CRAW4AI_COMMAND not set; skipping crawl4ai job."
    return 0
  fi
  local seeds_file
  seeds_file="$(mktemp)"
  cat >"$seeds_file" <<'EOF'
https://www.osha.gov/
https://www.cdc.gov/niosh/
https://sistemasinter.cetesb.sp.gov.br/produtos/produto_consulta_completa.asp
https://cameochemicals.noaa.gov/help/reactivity/reactive_groups.htm
https://safescience.cas.org/
https://www.cdc.gov/niosh/npg/npgdcas.html
EOF

  local timestamp output_file
  timestamp=$(date +%s)
  output_file="${CRAW4AI_OUTPUT_DIR:-./data/craw4ai}/crawl4ai_${timestamp}.json"
  mkdir -p "$(dirname "$output_file")"

  local cmd="${CRAW4AI_COMMAND}"
  cmd="${cmd//\{mode\}/url}"
  cmd="${cmd//\{input_file\}/$seeds_file}"
  cmd="${cmd//\{output_file\}/$output_file}"

  echo "Running: $cmd"
  if ! eval "$cmd"; then
    echo "crawl4ai run failed; skipping crawl ingestion."
    rm -f "$seeds_file"
    return 1
  fi
  rm -f "$seeds_file"

  if [[ -f "$output_file" ]]; then
    ingest_snapshot "$output_file"
  else
    echo "crawl4ai produced no output file at $output_file"
  fi
}

echo "== Simple URL ingestion =="
ingest_simple_urls || true

echo "== Google Custom Search ingestion (if configured) =="
ingest_google_search || true

echo "== crawl4ai job + ingestion (if configured) =="
run_crawl4ai || true

echo "Done."
