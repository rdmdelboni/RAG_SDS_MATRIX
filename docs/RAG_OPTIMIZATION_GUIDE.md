# RAG System Optimization Guide

## Overview

This guide covers the new RAG optimization and monitoring systems implemented to improve knowledge base quality and search performance.

## Components Implemented

### 1. Query Tracking System (`src/rag/query_tracker.py`)

Tracks all RAG queries, their performance metrics, and user feedback.

**What it does:**
- Logs every query with timing metrics (embedding time, search time, total time)
- Records which documents/chunks were returned
- Collects user feedback on result quality
- Calculates performance statistics and trends

**Database Tables Created:**
- `query_logs` - Individual query records
- `query_results` - Document/chunk results per query
- `query_feedback` - User ratings and notes
- `query_metrics` - Aggregated hourly/daily statistics

**Example Usage:**

```python
from src.database.db_manager import DatabaseManager
from src.rag.query_tracker import QueryTracker, QueryRecord

db = DatabaseManager()
tracker = QueryTracker(db)

# Log a query
query_record = QueryRecord(
    query_text="What is the flash point of acetone?",
    query_embedding_time=0.152,
    search_time=0.048,
    result_count=5,
    top_result_relevance=0.92,
    answer_generation_time=1.234,
    total_time=1.434,
    returned_document_ids=[1, 5, 12, 3, 8],
    returned_chunks=[0, 1, 0, 2, 0],
    user_id="user_123"
)
query_id = tracker.log_query(query_record)

# Get performance summary
stats = tracker.get_performance_summary(days=7)
print(f"Avg query time: {stats['avg_query_time_ms']}ms")

# Submit feedback on query
tracker.submit_feedback(
    query_id=query_id,
    rating="relevant",
    notes="Results were accurate and helpful",
    user_id="user_123"
)

# Analyze feedback
feedback = tracker.get_feedback_summary(days=7)
print(f"Quality: {feedback['relevant_percentage']}% of results marked relevant")

# Find problem queries
slow_queries = tracker.identify_low_performing_queries(threshold_percentile=90)
```

**Performance Metrics Available:**
- Total queries
- Average/min/max query time
- Embedding time
- Search time
- Result count
- User feedback ratings
- Quality percentages

### 2. Incremental Retrainer (`src/rag/incremental_retrainer.py`)

Automatically refreshes vector embeddings with new documents without full re-indexing.

**What it does:**
- Identifies documents added since last retraining
- Processes only new documents (efficient)
- Adds new embeddings to vector store
- Tracks retraining history
- Analyzes opportunities for knowledge base improvement

**Database Tables Created:**
- `retraining_history` - Records of all retraining sessions
- `retraining_state` - Tracks last retraining timestamp

**Example Usage:**

```python
from src.rag.incremental_retrainer import IncrementalRetrainer
from src.rag.vector_store import get_vector_store

vector_store = get_vector_store()
retrainer = IncrementalRetrainer(vector_store, db)

# Check if retraining should run
if retrainer.should_retrain(retraining_type="incremental", hours=24):
    result = retrainer.retrain_incremental(limit=1000)
    print(f"Retraining result: {result}")
    # Output: {
    #     "type": "incremental",
    #     "status": "success",
    #     "documents_processed": 25,
    #     "chunks_added": 342,
    #     "duration_seconds": 45.23
    # }

# Analyze opportunities
opportunities = retrainer.analyze_retraining_opportunities()
print(opportunities)
# Output: {
#     "low_chunk_documents": {...},
#     "exact_duplicates": {...},
#     "outdated_documents": {...},
#     "recent_ingestion_velocity": {...}
# }

# Get retraining history
history = retrainer.get_retraining_history(limit=10)
```

**Retraining Types:**
- `incremental` - Process only new documents (default, 24h interval)
- `full` - Re-embed all documents (weekly)
- `quick` - Quick index refresh (hourly)

### 3. Performance Analysis Script (`scripts/analyze_rag_performance.py`)

Standalone analysis tool that generates comprehensive performance reports.

**What it does:**
- Analyzes query performance patterns
- Rates result quality based on user feedback
- Identifies slowest/worst-performing queries
- Reviews knowledge base composition
- Generates prioritized optimization recommendations

**Usage:**

```bash
# Generate formatted report
python scripts/analyze_rag_performance.py --days 7

# Generate JSON output for integration
python scripts/analyze_rag_performance.py --days 7 --json > rag_analysis.json

# Show top 20 problem queries
python scripts/analyze_rag_performance.py --days 30 --top 20
```

**Report Sections:**
1. **Query Performance** - Speed and efficiency metrics
2. **Result Quality** - User feedback and satisfaction
3. **Problem Queries** - Slowest queries and those with no results
4. **Knowledge Base** - Document composition and growth
5. **Optimization Recommendations** - Prioritized action items

**Example Output:**
```
RAG SYSTEM PERFORMANCE ANALYSIS REPORT
Generated: 2025-11-28T14:32:10

1. QUERY PERFORMANCE
   Total Queries: 1,247
   Performance Tier: ACCEPTABLE
   Avg Query Time: 1,842.5ms
   Range: 245.3ms - 8,920.1ms
   Embedding: 152.3ms
   Search: 89.7ms

2. RESULT QUALITY (User Feedback)
   Quality Tier: GOOD
   Total Feedback: 156
   Relevant: 124
   Partially Relevant: 28
   Irrelevant: 4
   Quality Score: 79.5%

3. PROBLEM QUERIES (Top Issues)
   1. Query ID 4521
      Query: "compatibility between compounds x and y"
      Issue: slow_execution (7,234.5ms)
      Results: 5
      → Consider optimizing vector search or increasing chunk size

[... more recommendations ...]
```

## Integration Points

### Integrating Query Tracking into RAG Retriever

To enable automatic query tracking, wrap the retriever in your application:

```python
import time
from src.rag.retriever import RAGRetriever
from src.rag.query_tracker import QueryTracker, QueryRecord
from src.database.db_manager import DatabaseManager

db = DatabaseManager()
tracker = QueryTracker(db)
retriever = RAGRetriever()

def answer_with_tracking(query: str, k: int = 5) -> str:
    """Answer question and log performance metrics."""

    # Time the operations
    t_start = time.time()

    # Retrieve with timing
    t_embed_start = time.time()
    results = retriever.retrieve(query, k=k)
    t_search = time.time()

    # Extract metrics
    embedding_time = t_search - t_embed_start  # Approximate
    search_time = t_search - t_embed_start

    # Generate answer
    t_answer_start = time.time()
    answer = retriever.answer(query, k=k)
    t_total = time.time() - t_start
    answer_time = time.time() - t_answer_start

    # Log query
    record = QueryRecord(
        query_text=query,
        query_embedding_time=embedding_time,
        search_time=search_time,
        result_count=len(results),
        top_result_relevance=results[0].relevance_score if results else None,
        answer_generation_time=answer_time,
        total_time=t_total,
        returned_document_ids=[r.document_id for r in results],
        returned_chunks=[r.chunk_index for r in results],
    )
    query_id = tracker.log_query(record)

    return answer, query_id
```

### Setting Up Automated Retraining

Add to your application startup or task scheduler:

```python
import schedule
import time
from src.rag.incremental_retrainer import IncrementalRetrainer

retrainer = IncrementalRetrainer(vector_store, db)

def scheduled_retraining():
    """Run incremental retraining if needed."""
    if retrainer.should_retrain(retraining_type="incremental", hours=24):
        result = retrainer.retrain_incremental()
        logger.info(f"Incremental retraining: {result}")

# Schedule to run daily
schedule.every().day.at("02:00").do(scheduled_retraining)

# In your main loop:
while True:
    schedule.run_pending()
    time.sleep(60)
```

## Performance Optimization Workflow

### Step 1: Establish Baseline (Week 1)
```bash
# Run initial analysis
python scripts/analyze_rag_performance.py --days 1
```

**What to look for:**
- Current avg query time
- Current result quality (if any feedback)
- Knowledge base composition
- Any obvious problems

### Step 2: Collect Feedback (Week 2-3)

Implement user feedback UI in your application:
- Buttons to rate results as "Relevant / Partially / Irrelevant"
- Notes field for user comments

```python
# When user rates a result
tracker.submit_feedback(
    query_id=query_id,
    rating="relevant",
    notes="Results were accurate",
    user_id=current_user_id
)
```

### Step 3: Analyze & Optimize (Week 4+)

```bash
# Weekly analysis
python scripts/analyze_rag_performance.py --days 7
```

**Action by recommendation priority:**

**🔴 High Priority:**
- Poor query performance (>2s avg) → Optimize chunks/embedding
- Poor result quality (<60% relevant) → Improve chunking/domain handling

**🟡 Medium Priority:**
- Small knowledge base → Ingest more documents
- Exact duplicates → Clean up vector store
- Old documents → Re-ingest from sources

**🟢 Low Priority:**
- Marginal improvements
- Nice-to-have enhancements

## Recommended Configuration

### For Chemical SDS Documents (Your Use Case)

```python
# Optimal chunk settings for chemical documents
CHUNK_SIZE = 750  # Start here, test 500-1000
CHUNK_OVERLAP = 150
EMBEDDING_MODEL = "qwen3-embedding:4b"  # Current

# Test larger model if quality is low
# EMBEDDING_MODEL = "qwen3-embedding:7b"  # Better but slower
```

### Query Tracking Overhead

- Per-query overhead: ~10-30ms (minimal)
- Database storage: ~1KB per query
- No impact on retrieval speed

### Retraining Schedule

- **Incremental**: Daily (02:00 AM)
- **Full**: Weekly (Sunday 01:00 AM)
- **Quick**: Every 6 hours if high ingestion velocity

## Monitoring & Alerts

Create alerts for:

```python
# Alert if quality drops below 70%
feedback = tracker.get_feedback_summary(days=7)
if feedback.get('relevant_percentage', 0) < 70:
    send_alert("RAG quality below threshold")

# Alert if avg query time exceeds 2 seconds
perf = tracker.get_performance_summary(days=1)
if perf.get('avg_query_time_ms', 0) > 2000:
    send_alert("RAG queries slowing down")

# Alert if retraining fails
history = retrainer.get_retraining_history(limit=1)
if history and history[0]['status'] == 'failed':
    send_alert(f"Retraining failed: {history[0]['error']}")
```

## Troubleshooting

### Problem: "No query data yet"
**Solution:** System needs at least 24 hours of query logs. Use `--days 1` to see hourly data.

### Problem: "No user feedback data"
**Solution:** Implement feedback UI in your application. Users need to rate results.

### Problem: "Retraining failed"
**Causes:**
- Vector store connection issue
- Insufficient disk space
- Database lock

**Solution:** Check logs and retraining history table for error details.

### Problem: "Query performance degrading"
**Possible causes:**
1. Vector store growing too large
2. Embedding model overloaded
3. Too many low-quality documents

**Solutions:**
- Delete duplicates (use analysis tool)
- Increase chunk size (fewer embeddings)
- Use hybrid search (semantic + keyword)
- Upgrade embedding model

## Next Steps

After basic tracking is working:

1. **Implement Feedback UI** - Add rating buttons to query results
2. **Set Up Automated Retraining** - Run incremental retraining daily
3. **Weekly Analysis** - Run performance analysis script
4. **Implement Alerts** - Alert on quality/performance degradation
5. **Advanced Optimization** - Implement hybrid search, source-specific handlers

## Files Reference

```
Core System:
├── src/rag/query_tracker.py         # Query logging & feedback
├── src/rag/incremental_retrainer.py # Automatic re-indexing
└── src/rag/retriever.py             # Main RAG interface

Analysis Tools:
├── scripts/analyze_rag_performance.py # Performance analysis
└── docs/RAG_OPTIMIZATION_GUIDE.md    # This file

Database Tables:
├── query_logs                        # Individual queries
├── query_results                     # Documents returned
├── query_feedback                    # User ratings
├── query_metrics                     # Aggregated stats
├── retraining_history                # Retraining events
└── retraining_state                  # Current state tracking
```

## Questions & Support

For implementation questions, refer to:
- `src/rag/query_tracker.py` - Query tracking examples
- `src/rag/incremental_retrainer.py` - Retraining examples
- `scripts/analyze_rag_performance.py` - Analysis tool

Monitor your knowledge base quality continuously with these tools!
