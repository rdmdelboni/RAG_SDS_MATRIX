# Packaging & Lab Distribution (desktop UI)

## PyInstaller (Linux/macOS/Windows)
Build a single-folder bundle of the PySide6 UI (`main.py`):
```bash
python -m pip install pyinstaller
pyinstaller --name rag-sds-matrix --noconfirm --clean \
  --add-data "data:data" \
  --add-data "src/ui:src/ui" \
  --hidden-import PySide6 \
  main.py
```
Or use the helper script:
```bash
./scripts/package_ui.py --name rag-sds-matrix --onefile
```
Artifacts land in `dist/rag-sds-matrix/`. On Windows, add `--onefile` if you prefer a single exe (start slower).

Tips:
- Ensure Ollama, DuckDB data dirs, and `.env` are reachable; ship a sample `.env` beside the binary.
- For AppImage, wrap the PyInstaller output with appimagetool (outside scope of this doc).

## Experiment Packet CLI
Use `scripts/export_experiment_packet.py` to bundle matrix exports + SDS PDFs into a zip for lab handoff:
```bash
./scripts/export_experiment_packet.py --matrix data/output/matrix.csv \
  --sds-dir data/input/harvested \
  --cas 67-64-1 64-17-5 \
  --out packets
```
