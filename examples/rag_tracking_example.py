#!/usr/bin/env python3
"""
Example: How to integrate RAG query tracking into your application.

This shows the minimal code needed to add query tracking and feedback collection
to your existing RAG system.
"""

from __future__ import annotations

import time
from typing import Optional

from src.database.db_manager import DatabaseManager
from src.rag.query_tracker import QueryTracker, QueryRecord
from src.rag.retriever import RAGRetriever
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrackedRAGRetriever:
    """RAG retriever with automatic query tracking."""

    def __init__(self, user_id: Optional[str] = None):
        """Initialize tracked retriever.

        Args:
            user_id: Optional user identifier for feedback attribution
        """
        self.db = DatabaseManager()
        self.tracker = QueryTracker(self.db)
        self.retriever = RAGRetriever()
        self.user_id = user_id
        self.last_query_id = None

    def answer(self, query: str, k: int = 5) -> tuple[str, int]:
        """Answer a question and track performance metrics.

        Args:
            query: User question
            k: Number of documents to retrieve

        Returns:
            Tuple of (answer text, query_id for feedback)
        """
        # Time the entire operation
        t_start = time.time()

        # Get search results (the retriever.retrieve() internally does embedding)
        t_search_start = time.time()
        results = self.retriever.retrieve(query, k=k)
        t_search_end = time.time()

        # Generate answer with LLM
        t_answer_start = time.time()
        answer = self.retriever.answer(query, k=k)
        t_answer_end = time.time()

        # Calculate metrics
        total_time = time.time() - t_start
        search_time = t_search_end - t_search_start
        answer_time = t_answer_end - t_answer_start
        embedding_time = search_time * 0.3  # Rough estimate - embedding is ~30% of search time

        # Prepare record
        record = QueryRecord(
            query_text=query,
            query_embedding_time=embedding_time,
            search_time=search_time,
            result_count=len(results),
            top_result_relevance=results[0].relevance_score if results else None,
            answer_generation_time=answer_time,
            total_time=total_time,
            returned_document_ids=[r.document_id for r in results],
            returned_chunks=[r.chunk_index for r in results],
            user_id=self.user_id,
        )

        # Log the query
        self.last_query_id = self.tracker.log_query(record)

        # Log to console for debugging
        logger.info(
            f"Query logged (ID: {self.last_query_id}) | "
            f"Time: {total_time*1000:.1f}ms | "
            f"Results: {len(results)}"
        )

        return answer, self.last_query_id

    def submit_feedback(
        self,
        query_id: Optional[int] = None,
        rating: str = "relevant",
        notes: Optional[str] = None,
    ) -> bool:
        """Submit feedback on the last query or a specific query.

        Args:
            query_id: Query ID to rate (uses last query if None)
            rating: "relevant" | "partially_relevant" | "irrelevant"
            notes: Optional user notes/comments

        Returns:
            True if feedback was recorded successfully
        """
        if query_id is None:
            query_id = self.last_query_id

        if query_id is None:
            logger.warning("No query to rate - run answer() first")
            return False

        result = self.tracker.submit_feedback(
            query_id=query_id,
            rating=rating,
            notes=notes,
            user_id=self.user_id,
        )

        if result:
            logger.info(f"Feedback recorded for query {query_id}: {rating}")
        else:
            logger.error(f"Failed to record feedback for query {query_id}")

        return result

    def get_stats(self, days: int = 7) -> dict:
        """Get performance statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Performance statistics dictionary
        """
        return self.tracker.get_performance_summary(days=days)

    def get_feedback_stats(self, days: int = 7) -> dict:
        """Get feedback statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Feedback statistics dictionary
        """
        return self.tracker.get_feedback_summary(days=days)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================


def example_1_basic_usage():
    """Example 1: Basic usage - answer question and track it."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic Query Tracking")
    print("=" * 70)

    retriever = TrackedRAGRetriever(user_id="demo_user")

    # Ask a question
    question = "What are the main hazards of acetone?"
    print(f"\nQuestion: {question}")

    answer, query_id = retriever.answer(question, k=5)
    print(f"\nAnswer: {answer[:200]}...\n")
    print(f"✓ Query tracked with ID: {query_id}")


def example_2_with_feedback():
    """Example 2: Query tracking with user feedback."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Query Tracking + User Feedback")
    print("=" * 70)

    retriever = TrackedRAGRetriever(user_id="demo_user_2")

    # Ask a question
    question = "Flash point and flammability of methanol"
    print(f"\nQuestion: {question}")

    answer, query_id = retriever.answer(question, k=5)
    print(f"\nAnswer: {answer[:200]}...\n")

    # Simulate user rating the results
    print("Simulating user feedback...")
    retriever.submit_feedback(rating="relevant", notes="Results were accurate and helpful")
    print("✓ Feedback recorded\n")


def example_3_statistics():
    """Example 3: Get performance statistics."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Performance Statistics")
    print("=" * 70)

    retriever = TrackedRAGRetriever()

    # Get statistics
    stats = retriever.get_stats(days=7)

    if stats:
        print(f"\nPerformance Statistics (Last 7 Days):")
        print(f"  Total Queries: {stats.get('total_queries', 0)}")
        print(f"  Avg Query Time: {stats.get('avg_query_time_ms', 0):.1f}ms")
        print(f"  Min Query Time: {stats.get('min_query_time_ms', 0):.1f}ms")
        print(f"  Max Query Time: {stats.get('max_query_time_ms', 0):.1f}ms")
        print(f"  Avg Results: {stats.get('avg_result_count', 0):.1f}")
        print(f"  Embedding Time: {stats.get('components', {}).get('embedding_avg_ms', 0):.1f}ms")
        print(f"  Search Time: {stats.get('components', {}).get('search_avg_ms', 0):.1f}ms")
    else:
        print("\n✓ No query history yet - run some queries first!")

    # Get feedback statistics
    feedback = retriever.get_feedback_stats(days=7)
    if feedback.get("total_feedback", 0) > 0:
        print(f"\nFeedback Statistics (Last 7 Days):")
        print(f"  Total Feedback: {feedback.get('total_feedback', 0)}")
        print(f"  Relevant: {feedback.get('results', {}).get('relevant', 0)}")
        print(f"  Partially Relevant: {feedback.get('results', {}).get('partially_relevant', 0)}")
        print(f"  Irrelevant: {feedback.get('results', {}).get('irrelevant', 0)}")
        print(f"  Quality Score: {feedback.get('relevant_percentage', 0):.1f}%")
    else:
        print("\n  No feedback recorded yet")


def example_4_multiple_users():
    """Example 4: Track queries from multiple users."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Multi-User Tracking")
    print("=" * 70)

    users = ["alice@company.com", "bob@company.com", "charlie@company.com"]
    questions = [
        "What is the flash point of acetone?",
        "Health hazards of benzene",
        "Storage requirements for peroxides",
    ]

    print("\nSimulating queries from multiple users...\n")

    for user, question in zip(users, questions):
        retriever = TrackedRAGRetriever(user_id=user)
        print(f"  {user}: {question[:50]}...", end=" ")

        answer, query_id = retriever.answer(question, k=3)

        # Random feedback
        import random
        rating = random.choice(["relevant", "partially_relevant", "irrelevant"])
        retriever.submit_feedback(rating=rating)

        print(f"(ID: {query_id}, Rating: {rating})")

    print("\n✓ All queries tracked per user")


def example_5_integration_pattern():
    """Example 5: Integration pattern for your application."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Integration Pattern (How to use in your app)")
    print("=" * 70)

    print("""
# In your application code:

# 1. Initialize once at startup
rag = TrackedRAGRetriever(user_id=current_user.id)

# 2. When user asks a question
answer, query_id = rag.answer(
    query="What are the health effects of toluene?",
    k=5
)

# 3. Display answer to user
display_answer(answer)

# 4. After user rates the results (add buttons to UI)
if user_clicked_relevant_button:
    rag.submit_feedback(rating="relevant", notes=user_notes)
elif user_clicked_irrelevant_button:
    rag.submit_feedback(rating="irrelevant", notes=user_notes)

# 5. Periodically show performance stats to admins
stats = rag.get_stats(days=7)
admin_dashboard.update(stats)

# 6. Run analysis script daily
# python scripts/analyze_rag_performance.py --days 7
    """)


def example_6_error_handling():
    """Example 6: Error handling patterns."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Error Handling")
    print("=" * 70)

    retriever = TrackedRAGRetriever(user_id="demo_user")

    try:
        # This should work
        question = "Safety data for household chemicals"
        answer, query_id = retriever.answer(question)
        print(f"✓ Query successful (ID: {query_id})")

        # Try to submit feedback
        if retriever.submit_feedback(rating="relevant"):
            print("✓ Feedback submitted")
        else:
            print("⚠ Feedback submission failed")

    except Exception as e:
        logger.error(f"Error in RAG query: {e}")
        print(f"✗ Error: {e}")


# ============================================================================
# MAIN
# ============================================================================


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("RAG QUERY TRACKING - INTEGRATION EXAMPLES")
    print("=" * 70)
    print("\nThese examples show how to integrate query tracking into your app.\n")

    # Run examples
    example_1_basic_usage()
    example_2_with_feedback()
    example_3_statistics()
    example_4_multiple_users()
    example_5_integration_pattern()
    example_6_error_handling()

    print("\n" + "=" * 70)
    print("For more information, see docs/RAG_QUICK_START.md")
    print("=" * 70 + "\n")
