from functools import lru_cache

from sentence_transformers import SentenceTransformer

from embeddings.create_embeddings import vectorize_chunks

SEARCH_SQL = """
    SELECT
        c.id,
        c.title,
        c.content_type,
        p.photo_url,
        v.video_url,
        ce.source_type,
        ce.chunk_text,
        1 - (ce.embedding <=> %(query_vector)s::vector) AS similarity
    FROM CONTENT_EMBEDDING ce
    JOIN CONTENT c ON c.id = ce.content_id
    LEFT JOIN PHOTO p ON p.content_id = c.id
    LEFT JOIN VIDEO v ON v.content_id = c.id
    ORDER BY ce.embedding <=> %(query_vector)s::vector
    LIMIT %(limit)s
"""


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


from app.preferences import get_user_max_results

def search_content(conn, query_text: str, user_id: str = None, limit: int = None):
    if limit is None:
        limit = get_user_max_results(conn, user_id, default=10) if user_id else 10

    model = get_model()
    query_vector = vectorize_chunks(model, [query_text])[0]

    with conn.cursor() as cur:
        cur.execute(SEARCH_SQL, {"query_vector": query_vector, "limit": limit})
        return cur.fetchall()
