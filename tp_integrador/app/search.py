from functools import lru_cache

from sentence_transformers import SentenceTransformer

from embeddings.create_embeddings import vectorize_chunks

SEARCH_SQL = """
    SELECT
        c.id,
        c.title,
        c.content_type,
        ce.source_type,
        ce.chunk_text,
        1 - (ce.embedding <=> %(query_vector)s::vector) AS similarity
    FROM CONTENT_EMBEDDING ce
    JOIN CONTENT c ON c.id = ce.content_id
    ORDER BY ce.embedding <=> %(query_vector)s::vector
    LIMIT %(limit)s
"""


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


def search_content(conn, query_text, limit=10):
    model = get_model()
    query_vector = vectorize_chunks(model, [query_text])[0]

    with conn.cursor() as cur:
        cur.execute(SEARCH_SQL, {"query_vector": query_vector, "limit": limit})
        return cur.fetchall()
