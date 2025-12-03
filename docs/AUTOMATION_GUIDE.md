# Automation Guide

## Harvest scheduling
- Run once from a CAS list and process immediately:
  `./scripts/harvest_and_process.py --cas-file cas_list.txt --output data/input/harvested --process`
- Run on a schedule (polling loop):
  `./scripts/harvest_scheduler.py --cas-file cas_list.txt --interval 60 --process`
  (set `--iterations` to stop after N runs; default is infinite)
- Inventory sync (optional):
  - Copy mode: `OE_SYNC_ENABLED=true OE_SYNC_EXPORT_DIR=/tmp/stage ...`
  - MySQL mode: `OE_SYNC_ENABLED=true OE_SYNC_MODE=mysql OE_SYNC_DB_HOST=... OE_SYNC_DB_USER=... OE_SYNC_DB_PASSWORD=... OE_SYNC_DB_NAME=... ...`

## Experiment packets
Bundle matrix exports + SDS PDFs for lab handoff:
`./scripts/export_experiment_packet.py --matrix data/output/matrix.csv --sds-dir data/input/harvested --cas 67-64-1 64-17-5 --out packets`
