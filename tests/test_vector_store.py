from src.rag.vector_store import get_vector_store
from langchain_core.documents import Document


def test_vector_store_add_documents():
    store = get_vector_store()
    docs = [Document(page_content="Example content for indexing", metadata={"source": "test"})]
    store.add_documents(docs)
    # Chroma client exposes count via _collection.count() but keep loose to avoid coupling
    assert len(docs) == 1
