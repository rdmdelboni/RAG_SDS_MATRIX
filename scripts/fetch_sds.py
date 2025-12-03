#!/usr/bin/env python3
"""
Script to fetch SDS documents from the web.
"""
import argparse
import sys
import logging
from pathlib import Path
from typing import List

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.harvester.core import SDSHarvester
from src.utils.logger import get_logger

logger = get_logger("fetch_sds")

def main():
    parser = argparse.ArgumentParser(description="Fetch SDS documents by CAS number.")
    parser.add_argument("cas_numbers", nargs="+", help="List of CAS numbers to search for")
    parser.add_argument("--output", "-o", type=str, default="data/input/harvested", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)

    output_dir = Path(args.output)
    harvester = SDSHarvester()
    
    print(f"Initialized Harvester with {len(harvester.providers)} providers.")
    
    for cas in args.cas_numbers:
        print(f"Searching for CAS: {cas}...")
        results = harvester.find_sds(cas)
        
        if not results:
            print(f"No SDS found for {cas}")
            continue
            
        print(f"Found {len(results)} potential SDSs for {cas}.")
        
        # For now, just download the first one or all?
        # Let's download all unique ones up to a limit to avoid spam.
        
        for i, res in enumerate(results[:3]):
            print(f"  Downloading result {i+1}: {res.title} from {res.source}")
            file_path = harvester.download_sds(res, output_dir)
            if file_path:
                print(f"  ✅ Downloaded to {file_path}")
            else:
                print(f"  ❌ Failed to download {res.url}")

if __name__ == "__main__":
    main()
