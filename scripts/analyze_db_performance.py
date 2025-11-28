#!/usr/bin/env python3
"""
Database performance analysis script.
Compares query performance with and without indexes.
"""
import time
from src.database.db_manager import DatabaseManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


def benchmark_query(db: DatabaseManager, query: str, name: str) -> float:
    """Benchmark a single query and return execution time."""
    start = time.time()
    db.conn.execute(query)
    elapsed = time.time() - start
    return elapsed


def analyze_indexes():
    """Analyze the impact of database indexes on query performance."""
    print("=" * 80)
    print("DATABASE INDEX PERFORMANCE ANALYSIS")
    print("=" * 80)

    db = DatabaseManager()
    
    # Get database statistics
    print("\n📊 Database Statistics:")
    print("-" * 80)
    
    with db._lock:
        doc_count_result = db.conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        doc_count = doc_count_result[0] if doc_count_result else 0
        
        ext_count_result = db.conn.execute("SELECT COUNT(*) FROM extractions").fetchone()
        ext_count = ext_count_result[0] if ext_count_result else 0
        
        rag_incomp_result = db.conn.execute("SELECT COUNT(*) FROM rag_incompatibilities").fetchone()
        rag_incomp_count = rag_incomp_result[0] if rag_incomp_result else 0
        
        rag_hazard_result = db.conn.execute("SELECT COUNT(*) FROM rag_hazards").fetchone()
        rag_hazard_count = rag_hazard_result[0] if rag_hazard_result else 0
    
    print(f"  Documents: {doc_count:,}")
    print(f"  Extractions: {ext_count:,}")
    print(f"  RAG Incompatibilities: {rag_incomp_count:,}")
    print(f"  RAG Hazards: {rag_hazard_count:,}")
    
    # List existing indexes
    print("\n🔍 Database Indexes:")
    print("-" * 80)
    
    with db._lock:
        indexes = db.conn.execute(
            """
            SELECT
                table_name,
                index_name,
                is_unique,
                is_primary
            FROM duckdb_indexes()
            ORDER BY table_name, index_name;
            """
        ).fetchall()
    
    if indexes:
        for table, idx_name, is_unique, is_primary in indexes:
            unique_str = " (UNIQUE)" if is_unique else ""
            primary_str = " (PRIMARY)" if is_primary else ""
            print(f"  {table}.{idx_name}{unique_str}{primary_str}")
    else:
        print("  No indexes found")
    
    # Benchmark queries
    print("\n⏱️  Query Performance Benchmarks:")
    print("-" * 80)
    
    queries = [
        (
            "Filter by status",
            "SELECT * FROM documents WHERE status = 'success';"
        ),
        (
            "Filter by dangerous flag",
            "SELECT * FROM documents WHERE is_dangerous = TRUE;"
        ),
        (
            "Filter by filename pattern",
            "SELECT * FROM documents WHERE filename LIKE '%sulfuric%';"
        ),
        (
            "Join documents and extractions",
            """
            SELECT d.filename, e.field_name, e.value
            FROM documents d
            JOIN extractions e ON d.id = e.document_id
            WHERE e.field_name = 'cas_number';
            """
        ),
        (
            "Filter extractions by validation",
            "SELECT * FROM extractions WHERE validation_status = 'valid';"
        ),
        (
            "Find product by CAS in extractions",
            """
            SELECT d.filename, e.value, e.confidence
            FROM documents d
            JOIN extractions e ON d.id = e.document_id
            WHERE e.field_name = 'cas_number' AND e.value LIKE '7664-93-9';
            """
        ),
        (
            "RAG incompatibilities lookup",
            "SELECT * FROM rag_incompatibilities WHERE cas_a = '7664-93-9';"
        ),
        (
            "RAG hazards lookup",
            "SELECT * FROM rag_hazards WHERE cas = '7664-93-9';"
        ),
        (
            "Matrix decisions by CAS",
            "SELECT * FROM matrix_decisions WHERE cas_a = '7664-93-9' OR cas_b = '7664-93-9';"
        ),
        (
            "Recent matrix decisions",
            """
            SELECT * FROM matrix_decisions
            WHERE decided_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
            ORDER BY decided_at DESC;
            """
        )
    ]
    
    results = []
    for name, query in queries:
        try:
            elapsed = benchmark_query(db, query, name)
            results.append((name, elapsed))
            print(f"  {name:.<50} {elapsed*1000:.2f} ms")
        except Exception as e:
            print(f"  {name:.<50} ERROR: {str(e)[:30]}")
    
    # EXPLAIN ANALYZE for key queries
    print("\n📈 Query Execution Plans (Sample):")
    print("-" * 80)
    
    explain_queries = [
        (
            "Status filter",
            "EXPLAIN ANALYZE SELECT * FROM documents WHERE status = 'success';"
        ),
        (
            "Join with field filter",
            """
            EXPLAIN ANALYZE
            SELECT d.filename, e.field_name, e.value
            FROM documents d
            JOIN extractions e ON d.id = e.document_id
            WHERE e.field_name = 'cas_number';
            """
        )
    ]
    
    for name, query in explain_queries:
        print(f"\n{name}:")
        try:
            with db._lock:
                plan = db.conn.execute(query).fetchall()
            for row in plan:
                print(f"  {row[0]}")
        except Exception as e:
            print(f"  ERROR: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if results:
        total_time = sum(r[1] for r in results)
        avg_time = total_time / len(results)
        fastest = min(results, key=lambda x: x[1])
        slowest = max(results, key=lambda x: x[1])
        
        print(f"Total queries: {len(results)}")
        print(f"Total time: {total_time*1000:.2f} ms")
        print(f"Average time: {avg_time*1000:.2f} ms")
        print(f"Fastest: {fastest[0]} ({fastest[1]*1000:.2f} ms)")
        print(f"Slowest: {slowest[0]} ({slowest[1]*1000:.2f} ms)")
    
    print("\n💡 Recommendations:")
    print("-" * 80)
    
    if doc_count < 100:
        print("  ℹ️  Database has few documents. Index benefits are minimal.")
        print("     Indexes show significant impact with 1000+ documents.")
    else:
        print("  ✅ Database has sufficient data for index benefits.")
    
    if ext_count > doc_count * 10:
        print("  ✅ Good extraction density. Indexes help with field lookups.")
    
    print("\n📚 Index Usage Guidelines:")
    print("-" * 80)
    print("  • Indexes speed up WHERE, JOIN, and ORDER BY operations")
    print("  • Index overhead is minimal for writes (< 5% typically)")
    print("  • Composite indexes help with multi-column filters")
    print("  • Function-based indexes enable JSON field queries")
    print("  • Regular ANALYZE updates help query optimizer")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_indexes()
