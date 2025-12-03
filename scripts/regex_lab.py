"""Quick CLI to test manufacturer regex profiles against an SDS document."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sds.extractor import SDSExtractor  # noqa: E402
from src.sds.heuristics import HeuristicExtractor  # noqa: E402
from src.sds.profile_router import ProfileRouter  # noqa: E402
from src.sds.regex_catalog import RegexCatalog  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regex lab for SDS profiles.")
    parser.add_argument(
        "--file",
        type=Path,
        required=False,
        help="Path to SDS file (PDF or text).",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Force a specific manufacturer profile name (otherwise auto-detect).",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=None,
        help="Limit to specific fields (e.g., cas_number product_name).",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available regex profiles and exit.",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=80,
        help="Number of characters to show around a match.",
    )
    return parser.parse_args()


def list_profiles(router: ProfileRouter) -> None:
    print("Available profiles:")
    for name in router.list_profiles():
        print(f" - {name}")


def main() -> None:
    args = parse_args()
    router = ProfileRouter(regex_catalog=RegexCatalog())

    if args.list_profiles:
        list_profiles(router)
        return

    if not args.file:
        raise SystemExit("Please provide --file to test regexes.")

    extractor = SDSExtractor()
    heuristics = HeuristicExtractor()

    doc = extractor.extract_document(args.file)
    text = doc["text"]
    sections = doc.get("sections", {})

    profile = router.identify_profile(text, preferred=args.profile)
    print(f"Profile selected: {profile.name} (source={profile.source}, version={profile.version})")

    results = heuristics.extract_all_fields(text, sections, profile=profile)
    if args.fields:
        results = {k: v for k, v in results.items() if k in set(args.fields)}

    if not results:
        print("No matches found with current profile.")
        return

    for field, result in results.items():
        value = result.get("value")
        context = result.get("context", "")
        print(f"\n[{field}]")
        print(f"  value      : {value}")
        print(f"  confidence : {result.get('confidence'):.2f}")
        print(f"  source     : {result.get('source')}")
        if context:
            snippet = context[: args.context] + ("..." if len(context) > args.context else "")
            print(f"  context    : {snippet}")


if __name__ == "__main__":
    main()
