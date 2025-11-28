#!/usr/bin/env python3
"""
Monitor CAMEO ingestion progress in real-time.

Shows:
- Chemicals processed so far
- Success/failure rates
- Estimated time remaining
- Current letter being processed
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def get_log_stats() -> dict:
    """Extract statistics from the ingestion log."""
    log_file = project_root / "data" / "logs" / "ingest_cameo_chemicals.log"

    if not log_file.exists():
        return {}

    try:
        log_content = log_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    stats = {
        "total_found": 0,
        "total_ingested": 0,
        "total_failed": 0,
        "current_letter": None,
        "processed_letters": [],
        "lines": log_content.split("\n"),
    }

    # Parse log for statistics
    for line in stats["lines"]:
        if "Processing letter" in line:
            # Extract letter: "Processing letter 'A'"
            for char in line:
                if char.isalpha() and len(char) == 1:
                    stats["current_letter"] = char
                    break

        if "Found" in line and "chemicals for letter" in line:
            # "Found 443 unique chemicals for letter 'A'"
            try:
                parts = line.split("Found ")
                if len(parts) > 1:
                    num = int(parts[1].split()[0])
                    stats["total_found"] += num
            except Exception:
                pass

        if "Ingested:" in line and "chunks" in line:
            # "✓ Ingested: Acetone (ID: 18052, 3 chunks)"
            stats["total_ingested"] += 1

        if "Failed to scrape" in line:
            stats["total_failed"] += 1

        if "Processing letter" in line:
            for char in line:
                if (
                    char.isalpha()
                    and len(char) == 1
                    and char not in stats["processed_letters"]
                ):
                    stats["processed_letters"].append(char)
                    break

    return stats


def format_duration(seconds: int) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def calculate_eta(processed: int, total: int, elapsed: int) -> str:
    """Calculate estimated time to completion."""
    if processed == 0:
        return "unknown"

    rate = processed / elapsed if elapsed > 0 else 0
    remaining = total - processed
    eta_seconds = remaining / rate if rate > 0 else 0

    return format_duration(int(eta_seconds))


def print_progress_bar(processed: int, total: int, width: int = 50) -> str:
    """Print a progress bar."""
    if total == 0:
        return "N/A"

    percentage = (processed / total) * 100
    filled = int((percentage / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {percentage:.1f}%"


def main():
    """Main monitoring loop."""
    print("\n" + "=" * 70)
    print("  📊 CAMEO Ingestion Monitor")
    print("=" * 70)

    # Check if ingestion is running
    log_file = project_root / "data" / "logs" / "ingest_cameo_chemicals.log"
    if not log_file.exists():
        print("\n⚠️  No ingestion log found at:")
        print(f"   {log_file}")
        print("\nStart ingestion with:")
        print("   python scripts/ingest_cameo_chemicals.py")
        return 1

    # Check if still running
    try:
        last_modified = datetime.fromtimestamp(log_file.stat().st_mtime)
        age = (datetime.now() - last_modified).total_seconds()

        if age > 300:  # 5 minutes old
            print("\n⚠️  Ingestion log is 5+ minutes old. Is the process still running?")
            print(f"Last update: {last_modified.strftime('%H:%M:%S')}")
    except Exception:
        pass

    # Display continuous updates
    last_stats = None
    start_time = time.time()

    try:
        print("\nMonitoring ingestion progress (Ctrl+C to exit)...\n")

        while True:
            stats = get_log_stats()

            if not stats or not stats["lines"]:
                print("Waiting for data...")
                time.sleep(2)
                continue

            # Only print if stats changed
            if stats != last_stats:
                # Calculate metrics
                total_chemicals = stats["total_found"]
                ingested = stats["total_ingested"]
                failed = stats["total_failed"]
                current = stats["current_letter"] or "?"
                elapsed = int(time.time() - start_time)

                # Clear screen (simple version - works on most terminals)
                print("\033[2J\033[H", end="")  # Clear screen and move cursor home

                print("=" * 70)
                print("  📊 CAMEO Ingestion Monitor")
                print("=" * 70)

                # Current status
                print(f"\n📍 Currently processing: Letter '{current}'")
                if stats["processed_letters"]:
                    print(
                        f"   Completed: {', '.join(sorted(stats['processed_letters']))}"
                    )

                # Overall statistics
                print(f"\n📈 Statistics:")
                print(f"   Found: {total_chemicals} chemicals")
                print(f"   Ingested: {ingested}")
                print(f"   Failed: {failed}")

                if total_chemicals > 0:
                    success_rate = (ingested / total_chemicals) * 100
                    print(f"   Success Rate: {success_rate:.1f}%")

                # Progress bar
                if total_chemicals > 0:
                    print(
                        f"\n📊 Progress: {print_progress_bar(ingested, total_chemicals)}"
                    )
                else:
                    print(f"\n📊 Progress: (calculating...)")

                # Time information
                if ingested > 0 and elapsed > 0:
                    rate = ingested / (elapsed / 3600)  # chemicals per hour
                    eta = calculate_eta(ingested, total_chemicals, elapsed)
                    print(f"\n⏱️  Time Information:")
                    print(f"   Elapsed: {format_duration(elapsed)}")
                    print(f"   ETA: {eta}")
                    print(f"   Rate: {rate:.1f} chemicals/hour")

                # Estimated total time
                if ingested > 0:
                    avg_time_per_chemical = elapsed / ingested
                    total_estimate = avg_time_per_chemical * total_chemicals
                    print(f"   Total Estimate: {format_duration(int(total_estimate))}")

                # Last update
                print(f"\n🔄 Last update: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 70)

                last_stats = stats

            time.sleep(5)  # Update every 5 seconds

    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped by user")

        # Show final stats
        stats = get_log_stats()
        if stats:
            print("\n" + "=" * 70)
            print("FINAL STATISTICS")
            print("=" * 70)
            print(f"Chemicals Found: {stats['total_found']}")
            print(f"Successfully Ingested: {stats['total_ingested']}")
            print(f"Failed: {stats['total_failed']}")
            print("=" * 70)

        return 0


if __name__ == "__main__":
    sys.exit(main())
