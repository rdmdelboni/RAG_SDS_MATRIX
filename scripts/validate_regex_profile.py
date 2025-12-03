#!/usr/bin/env python3
"""Validate regex profile against test samples.

Usage:
    python scripts/validate_regex_profile.py \\
        --profile data/regex/profiles/yourmanufacturer.json \\
        --samples data/regex/extracted/YourManufacturer/
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def load_profile(profile_path: Path) -> Dict:
    """Load and validate profile JSON."""
    try:
        with open(profile_path) as f:
            profile = json.load(f)
        
        # Validate required fields
        required = ['manufacturer', 'priority', 'patterns']
        missing = [f for f in required if f not in profile]
        if missing:
            console.print(f"[red]❌ Missing required fields: {missing}[/red]")
            return None
        
        # Validate patterns compile
        invalid_patterns = []
        for name, pattern in profile['patterns'].items():
            try:
                re.compile(pattern, re.DOTALL | re.MULTILINE)
            except re.error as e:
                invalid_patterns.append((name, str(e)))
        
        if invalid_patterns:
            console.print("[red]❌ Invalid regex patterns:[/red]")
            for name, error in invalid_patterns:
                console.print(f"  • {name}: {error}")
            return None
        
        console.print(f"[green]✅ Profile loaded:[/green] {profile['manufacturer']}")
        return profile
        
    except json.JSONDecodeError as e:
        console.print(f"[red]❌ Invalid JSON: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Error loading profile: {e}[/red]")
        return None


def load_samples(samples_dir: Path) -> List[Tuple[Path, str]]:
    """Load all text samples from directory."""
    samples = []
    
    if not samples_dir.exists():
        console.print(f"[yellow]⚠️  Sample directory not found: {samples_dir}[/yellow]")
        return samples
    
    for txt_file in samples_dir.glob("*.txt"):
        try:
            content = txt_file.read_text(encoding='utf-8')
            samples.append((txt_file, content))
        except Exception as e:
            console.print(f"[yellow]⚠️  Failed to read {txt_file.name}: {e}[/yellow]")
    
    console.print(f"[blue]📄 Loaded {len(samples)} sample files[/blue]")
    return samples


def test_pattern(pattern: str, text: str, field_name: str) -> Tuple[bool, str, float]:
    """Test a single pattern against text.
    
    Returns:
        (success, extracted_value, confidence)
    """
    try:
        regex = re.compile(pattern, re.DOTALL | re.MULTILINE)
        match = regex.search(text)
        
        if match:
            value = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            value = value.strip()
            
            # Calculate confidence based on value quality
            confidence = 1.0
            if len(value) < 3:
                confidence *= 0.5  # Very short extractions
            if not any(c.isalnum() for c in value):
                confidence *= 0.3  # No alphanumeric chars
            if len(value) > 200:
                confidence *= 0.7  # Suspiciously long
            
            return True, value, confidence
        else:
            return False, "", 0.0
            
    except Exception as e:
        return False, f"Error: {e}", 0.0


def validate_profile(profile: Dict, samples: List[Tuple[Path, str]]) -> Dict:
    """Validate profile against all samples.
    
    Returns:
        Summary statistics and detailed results
    """
    results = {
        'total_samples': len(samples),
        'total_fields': len(profile['patterns']),
        'field_results': {},
        'sample_results': []
    }
    
    # Test each pattern across all samples
    for field_name, pattern in profile['patterns'].items():
        field_stats = {
            'successes': 0,
            'failures': 0,
            'avg_confidence': 0.0,
            'samples': []
        }
        
        confidences = []
        
        for sample_path, sample_text in samples:
            success, value, confidence = test_pattern(pattern, sample_text, field_name)
            
            field_stats['samples'].append({
                'file': sample_path.name,
                'success': success,
                'value': value[:100] if value else "",  # Truncate
                'confidence': confidence
            })
            
            if success:
                field_stats['successes'] += 1
                confidences.append(confidence)
            else:
                field_stats['failures'] += 1
        
        field_stats['avg_confidence'] = sum(confidences) / len(confidences) if confidences else 0.0
        results['field_results'][field_name] = field_stats
    
    # Test samples against validation test cases
    if 'validation' in profile and 'test_cases' in profile['validation']:
        results['test_cases'] = []
        
        for test_case in profile['validation']['test_cases']:
            test_file = test_case.get('file')
            expected = test_case.get('expected', {})
            
            # Find matching sample
            sample_text = None
            for sample_path, text in samples:
                if sample_path.name == test_file:
                    sample_text = text
                    break
            
            if not sample_text:
                results['test_cases'].append({
                    'file': test_file,
                    'status': 'MISSING',
                    'matches': {}
                })
                continue
            
            # Test expected fields
            matches = {}
            all_match = True
            
            for field, expected_value in expected.items():
                if field not in profile['patterns']:
                    continue
                
                success, actual_value, confidence = test_pattern(
                    profile['patterns'][field],
                    sample_text,
                    field
                )
                
                matches[field] = {
                    'expected': expected_value,
                    'actual': actual_value,
                    'match': expected_value.lower() in actual_value.lower() if actual_value else False,
                    'confidence': confidence
                }
                
                if not matches[field]['match']:
                    all_match = False
            
            results['test_cases'].append({
                'file': test_file,
                'status': 'PASS' if all_match else 'FAIL',
                'matches': matches
            })
    
    return results


def display_results(profile: Dict, results: Dict) -> None:
    """Display validation results with rich formatting."""
    
    # Header
    console.print()
    console.print(Panel(
        f"[bold cyan]{profile['manufacturer']}[/bold cyan]\n"
        f"Priority: {profile['priority']} | "
        f"Samples: {results['total_samples']} | "
        f"Fields: {results['total_fields']}",
        title="Regex Profile Validation",
        box=box.DOUBLE
    ))
    console.print()
    
    # Field Summary Table
    table = Table(title="Field Extraction Results", box=box.ROUNDED)
    table.add_column("Field", style="cyan")
    table.add_column("Success Rate", justify="right")
    table.add_column("Avg Confidence", justify="right")
    table.add_column("Status", justify="center")
    
    total_success_rate = 0
    
    for field_name, stats in results['field_results'].items():
        success_rate = stats['successes'] / results['total_samples'] * 100
        total_success_rate += success_rate
        avg_conf = stats['avg_confidence']
        
        # Status emoji
        if success_rate >= 90 and avg_conf >= 0.8:
            status = "✅"
            style = "green"
        elif success_rate >= 70:
            status = "⚠️"
            style = "yellow"
        else:
            status = "❌"
            style = "red"
        
        table.add_row(
            field_name,
            f"[{style}]{success_rate:.1f}%[/{style}]",
            f"[{style}]{avg_conf:.2f}[/{style}]",
            status
        )
    
    console.print(table)
    console.print()
    
    # Overall Score
    overall_score = total_success_rate / len(results['field_results'])
    score_style = "green" if overall_score >= 90 else "yellow" if overall_score >= 70 else "red"
    
    console.print(Panel(
        f"[bold {score_style}]{overall_score:.1f}%[/bold {score_style}]",
        title="Overall Success Rate",
        box=box.HEAVY
    ))
    console.print()
    
    # Test Cases
    if 'test_cases' in results and results['test_cases']:
        console.print("[bold]Validation Test Cases:[/bold]")
        
        for test_case in results['test_cases']:
            status = test_case['status']
            icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
            
            console.print(f"{icon} {test_case['file']}: [{status}]")
            
            if test_case.get('matches'):
                for field, match_info in test_case['matches'].items():
                    if match_info['match']:
                        console.print(f"   ✓ {field}: [green]{match_info['actual'][:50]}[/green]")
                    else:
                        console.print(f"   ✗ {field}:")
                        console.print(f"     Expected: [yellow]{match_info['expected']}[/yellow]")
                        console.print(f"     Got: [red]{match_info['actual'][:50]}[/red]")
        
        console.print()
    
    # Recommendations
    console.print("[bold]Recommendations:[/bold]")
    
    if overall_score >= 90:
        console.print("✅ Profile is ready for production use!")
    elif overall_score >= 70:
        console.print("⚠️  Profile works but could be improved:")
        
        # Find weak fields
        weak_fields = [
            name for name, stats in results['field_results'].items()
            if stats['successes'] / results['total_samples'] < 0.7
        ]
        
        if weak_fields:
            console.print(f"   • Strengthen patterns for: {', '.join(weak_fields)}")
    else:
        console.print("❌ Profile needs significant improvement:")
        console.print("   • Test patterns individually in regex tester")
        console.print("   • Add more flexible matching (\\s*, optional groups)")
        console.print("   • Check PDF text extraction quality")
    
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Validate regex profile")
    parser.add_argument("--profile", type=Path, required=True,
                       help="Path to profile JSON")
    parser.add_argument("--samples", type=Path, required=True,
                       help="Directory with sample text files")
    
    args = parser.parse_args()
    
    # Load profile
    profile = load_profile(args.profile)
    if not profile:
        return 1
    
    # Load samples
    samples = load_samples(args.samples)
    if not samples:
        console.print("[red]❌ No samples found[/red]")
        return 1
    
    # Validate
    console.print("\n[bold blue]Running validation...[/bold blue]")
    results = validate_profile(profile, samples)
    
    # Display
    display_results(profile, results)
    
    return 0


if __name__ == "__main__":
    exit(main())
