#!/usr/bin/env python3
"""RAG system performance analysis and optimization recommendations.

This script analyzes RAG query performance, identifies bottlenecks, and provides
optimization recommendations based on actual query patterns and user feedback.

Usage:
    python scripts/analyze_rag_performance.py [--days 7] [--top 20]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db_manager import DatabaseManager
from src.config.settings import get_settings
from src.rag.query_tracker import QueryTracker
from src.rag.incremental_retrainer import IncrementalRetrainer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAGPerformanceAnalyzer:
    """Analyze RAG system performance and provide recommendations."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize analyzer.

        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        self.tracker = QueryTracker(db_manager)
        self.retrainer = IncrementalRetrainer(None, db_manager)

    def analyze_query_performance(self, days: int = 7) -> dict[str, Any]:
        """Analyze query performance patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Performance analysis results
        """
        summary = self.tracker.get_performance_summary(days=days)

        if not summary:
            return {
                "status": "no_data",
                "message": "No query performance data available",
            }

        # Identify performance tiers
        avg_time = summary.get("avg_query_time_ms", 0)
        performance_tier = "good"

        if avg_time > 5000:  # > 5 seconds
            performance_tier = "poor"
        elif avg_time > 2000:  # > 2 seconds
            performance_tier = "acceptable"
        elif avg_time < 500:  # < 500ms
            performance_tier = "excellent"

        return {
            "analysis_period_days": days,
            "total_queries": summary.get("total_queries", 0),
            "avg_query_time_ms": summary.get("avg_query_time_ms", 0),
            "min_query_time_ms": summary.get("min_query_time_ms", 0),
            "max_query_time_ms": summary.get("max_query_time_ms", 0),
            "performance_tier": performance_tier,
            "components": {
                "embedding_avg_ms": summary.get("avg_embedding_time_ms", 0),
                "search_avg_ms": summary.get("avg_search_time_ms", 0),
            },
            "avg_results_per_query": summary.get("avg_result_count", 0),
            "queries_with_results": summary.get("queries_with_results", 0),
        }

    def analyze_feedback_quality(self, days: int = 7) -> dict[str, Any]:
        """Analyze user feedback patterns.

        Args:
            days: Number of days to analyze

        Returns:
            Feedback analysis results
        """
        feedback = self.tracker.get_feedback_summary(days=days)

        if not feedback or feedback.get("total_feedback", 0) == 0:
            return {
                "status": "no_feedback",
                "message": "No user feedback recorded yet",
                "recommendation": "Implement user feedback UI to gather quality data",
            }

        relevant_pct = feedback.get("relevant_percentage", 0)
        quality_tier = "poor"

        if relevant_pct >= 80:
            quality_tier = "excellent"
        elif relevant_pct >= 60:
            quality_tier = "good"
        elif relevant_pct >= 40:
            quality_tier = "acceptable"

        return {
            "analysis_period_days": days,
            "total_feedback_responses": feedback.get("total_feedback", 0),
            "quality_tier": quality_tier,
            "results": {
                "relevant": feedback.get("relevant", 0),
                "partially_relevant": feedback.get("partially_relevant", 0),
                "irrelevant": feedback.get("irrelevant", 0),
            },
            "relevant_percentage": feedback.get("relevant_percentage", 0),
        }

    def identify_problem_queries(self, top_n: int = 10) -> dict[str, Any]:
        """Identify slowest and worst-performing queries.

        Args:
            top_n: Number of problem queries to return

        Returns:
            List of problematic queries with analysis
        """
        queries = self.tracker.identify_low_performing_queries(threshold_percentile=75)[:top_n]

        if not queries:
            return {
                "status": "no_problems_detected",
                "message": "All queries performing within normal parameters",
            }

        problems = []

        for query in queries:
            issue = None
            recommendation = None

            if query["result_count"] == 0:
                issue = "no_results_returned"
                recommendation = "Query may be too specific or vector store may lack relevant documents"
            elif query["total_time_ms"] > 5000:
                issue = "slow_execution"
                recommendation = "Consider optimizing vector search or increasing chunk size"
            else:
                issue = "low_result_count"
                recommendation = "Consider adjusting search radius or improving document chunking"

            problems.append({
                "query_id": query["query_id"],
                "query_text": query["query_text"][:100],
                "issue": issue,
                "time_ms": query["total_time_ms"],
                "result_count": query["result_count"],
                "recommendation": recommendation,
            })

        return {
            "total_problems": len(problems),
            "problems": problems,
        }

    def analyze_knowledge_base(self) -> dict[str, Any]:
        """Analyze knowledge base composition and opportunities.

        Returns:
            Knowledge base analysis
        """
        opportunities = self.retrainer.analyze_retraining_opportunities()

        with self.db._lock:
            # Get document statistics
            doc_stats = self.db.conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN source_type = 'sds_document' THEN 1 END) as sds,
                    COUNT(CASE WHEN source_type = 'website' THEN 1 END) as websites,
                    COUNT(CASE WHEN source_type = 'structured_data' THEN 1 END) as structured,
                    SUM(chunk_count) as total_chunks,
                    AVG(chunk_count) as avg_chunks
                FROM rag_documents
                """
            ).fetchall()

            if doc_stats:
                row = doc_stats[0]
                return {
                    "total_documents": int(row[0]) if row[0] else 0,
                    "document_breakdown": {
                        "sds_documents": int(row[1]) if row[1] else 0,
                        "websites": int(row[2]) if row[2] else 0,
                        "structured_data": int(row[3]) if row[3] else 0,
                    },
                    "total_chunks": int(row[4]) if row[4] else 0,
                    "avg_chunks_per_doc": round(float(row[5]), 2) if row[5] else 0,
                    "opportunities": opportunities,
                }

        return {}

    def generate_recommendations(self) -> dict[str, Any]:
        """Generate optimization recommendations based on analysis.

        Returns:
            Prioritized recommendations
        """
        recommendations = []

        # Check query performance
        perf = self.analyze_query_performance(days=7)
        if perf.get("performance_tier") in ("poor", "acceptable"):
            recommendations.append({
                "priority": "high",
                "area": "query_performance",
                "issue": f"Average query time is {perf.get('avg_query_time_ms', 0):.0f}ms",
                "actions": [
                    "Optimize chunk size for your domain (test 500, 750, 1000, 1500 token sizes)",
                    "Consider using larger embedding model if hardware allows",
                    "Implement hybrid search (semantic + keyword) for better recall",
                    "Analyze slow queries for patterns (see problem_queries section)",
                ],
            })

        # Check feedback quality
        feedback = self.analyze_feedback_quality(days=7)
        if feedback.get("quality_tier") in ("poor", "acceptable"):
            recommendations.append({
                "priority": "high",
                "area": "result_quality",
                "issue": f"Only {feedback.get('relevant_percentage', 0):.1f}% of results marked relevant",
                "actions": [
                    "Implement user feedback mechanism (already built in)",
                    "Review low-performing queries and improve chunking strategy",
                    "Consider adding domain-specific preprocessing for SDS documents",
                    "Analyze feedback patterns to identify knowledge gaps",
                ],
            })

        # Check knowledge base
        kb = self.analyze_knowledge_base()
        if kb.get("total_documents", 0) < 50:
            recommendations.append({
                "priority": "medium",
                "area": "knowledge_base_growth",
                "issue": f"Knowledge base is small ({kb.get('total_documents', 0)} documents)",
                "actions": [
                    "Increase document ingestion from multiple sources",
                    "Set up automated daily ingestion from web sources",
                    "Ingest all available SDS documents from suppliers",
                ],
            })

        # Check for duplicates
        opps = kb.get("opportunities", {})
        if opps.get("exact_duplicates", {}).get("count", 0) > 0:
            recommendations.append({
                "priority": "medium",
                "area": "data_quality",
                "issue": f"Found {opps['exact_duplicates']['count']} duplicate documents",
                "actions": [
                    "Remove exact duplicate documents",
                    "Implement deduplication checks in ingestion pipeline",
                    "Clean up vector store to remove duplicate embeddings",
                ],
            })

        return {
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
        }

    def print_report(self, days: int = 7):
        """Print formatted analysis report.

        Args:
            days: Number of days to analyze
        """
        print("\n" + "=" * 80)
        print("RAG SYSTEM PERFORMANCE ANALYSIS REPORT".center(80))
        print(f"Generated: {datetime.now().isoformat()}".center(80))
        print(f"Analysis Period: {days} days".center(80))
        print("=" * 80 + "\n")

        # Query Performance
        print("1. QUERY PERFORMANCE")
        print("-" * 80)
        perf = self.analyze_query_performance(days=days)
        print(f"   Total Queries: {perf.get('total_queries', 0)}")
        print(f"   Performance Tier: {perf.get('performance_tier', 'unknown').upper()}")
        print(f"   Avg Query Time: {perf.get('avg_query_time_ms', 0):.1f}ms")
        print(f"   Range: {perf.get('min_query_time_ms', 0):.1f}ms - {perf.get('max_query_time_ms', 0):.1f}ms")
        print(f"   Embedding: {perf.get('components', {}).get('embedding_avg_ms', 0):.1f}ms")
        print(f"   Search: {perf.get('components', {}).get('search_avg_ms', 0):.1f}ms\n")

        # Feedback Quality
        print("2. RESULT QUALITY (User Feedback)")
        print("-" * 80)
        feedback = self.analyze_feedback_quality(days=days)
        if feedback.get("status") == "no_feedback":
            print("   ⚠ No user feedback data yet - implement feedback UI\n")
        else:
            print(f"   Quality Tier: {feedback.get('quality_tier', 'unknown').upper()}")
            print(f"   Total Feedback: {feedback.get('total_feedback_responses', 0)}")
            print(f"   Relevant: {feedback.get('results', {}).get('relevant', 0)}")
            print(f"   Partially Relevant: {feedback.get('results', {}).get('partially_relevant', 0)}")
            print(f"   Irrelevant: {feedback.get('results', {}).get('irrelevant', 0)}")
            print(f"   Quality Score: {feedback.get('relevant_percentage', 0):.1f}%\n")

        # Problem Queries
        print("3. PROBLEM QUERIES (Top Issues)")
        print("-" * 80)
        problems = self.identify_problem_queries(top_n=5)
        if problems.get("status") == "no_problems_detected":
            print("   ✓ All queries performing normally\n")
        else:
            for i, problem in enumerate(problems.get("problems", []), 1):
                print(f"   {i}. Query ID {problem['query_id']}")
                print(f"      Query: {problem['query_text']}")
                print(f"      Issue: {problem['issue']} ({problem['time_ms']:.1f}ms)")
                print(f"      Results: {problem['result_count']}")
                print(f"      → {problem['recommendation']}\n")

        # Knowledge Base
        print("4. KNOWLEDGE BASE")
        print("-" * 80)
        kb = self.analyze_knowledge_base()
        print(f"   Total Documents: {kb.get('total_documents', 0)}")
        print(f"   Total Chunks: {kb.get('total_chunks', 0)}")
        breakdown = kb.get("document_breakdown", {})
        print(f"   • SDS Documents: {breakdown.get('sds_documents', 0)}")
        print(f"   • Websites: {breakdown.get('websites', 0)}")
        print(f"   • Structured Data: {breakdown.get('structured_data', 0)}")
        print(f"   Avg Chunks/Doc: {kb.get('avg_chunks_per_doc', 0)}\n")

        # Recommendations
        print("5. OPTIMIZATION RECOMMENDATIONS")
        print("-" * 80)
        recs = self.generate_recommendations()
        for i, rec in enumerate(recs.get("recommendations", []), 1):
            priority_indicator = "🔴" if rec["priority"] == "high" else "🟡" if rec["priority"] == "medium" else "🟢"
            print(f"   {priority_indicator} [{rec['priority'].upper()}] {rec['area']}")
            print(f"      Issue: {rec['issue']}")
            for action in rec.get("actions", []):
                print(f"      • {action}")
            print()

        print("=" * 80)
        print("END OF REPORT".center(80))
        print("=" * 80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze RAG system performance and provide optimization recommendations"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to analyze (default: 7)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of problem queries to show (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of formatted report",
    )

    args = parser.parse_args()

    # Initialize
    settings = get_settings()
    db_manager = DatabaseManager()
    analyzer = RAGPerformanceAnalyzer(db_manager)

    if args.json:
        # JSON output
        report = {
            "timestamp": datetime.now().isoformat(),
            "analysis_period_days": args.days,
            "query_performance": analyzer.analyze_query_performance(days=args.days),
            "feedback_quality": analyzer.analyze_feedback_quality(days=args.days),
            "problem_queries": analyzer.identify_problem_queries(top_n=args.top),
            "knowledge_base": analyzer.analyze_knowledge_base(),
            "recommendations": analyzer.generate_recommendations(),
        }
        print(json.dumps(report, indent=2, default=str))
    else:
        # Formatted report
        analyzer.print_report(days=args.days)


if __name__ == "__main__":
    main()
