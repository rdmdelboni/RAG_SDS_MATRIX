# SDS Harvester Guide

The SDS Harvester is a new module designed to automate the discovery and downloading of Safety Data Sheets (SDS) from the web using CAS numbers.

## Features

- **Multi-Provider Architecture**: Extensible design allowing multiple data sources.
- **Current Providers**:
  - Fisher Scientific (Scraping)
  - ChemicalBook (Scraping)
  - ChemicalSafety.com (Scraping)
- **CLI Tool**: Easy-to-use command line interface.

## Usage

Run the `fetch_sds.py` script from the project root:

```bash
./scripts/fetch_sds.py [CAS_NUMBER_1] [CAS_NUMBER_2] ...
```

### Example

```bash
./scripts/fetch_sds.py 67-64-1 7664-93-9 --output data/input/new_sds
```

## Implementation Details

The core logic resides in `src/harvester/`.
- `base.py`: Defines the `BaseSDSProvider` interface.
- `core.py`: Manages providers and parallel execution.
- `providers/`: Contains specific provider implementations.

## Limitations

- **Bot Protection**: Many chemical vendors block automated requests. The current implementation uses `requests` with browser headers, but may still be blocked (403/404 errors).
- **Future Improvements**: Integrating `selenium` or `playwright` would significantly improve success rates by handling JavaScript and CAPTCHAs.
