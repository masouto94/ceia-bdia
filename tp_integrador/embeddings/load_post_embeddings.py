import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from create_embeddings import chunk_sentences, vectorize_chunks

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_CONFIG = {
    "host": os.environ["PGHOST"],
    "port": os.environ["PGPORT"],
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
}

SELECT_POSTS = """
    SELECT post.id AS post_id, content.title
    FROM POST post
    JOIN CONTENT content ON content.id = post.content_id
"""

UPSERT_EMBEDDING = """
    INSERT INTO POST_EMBEDDING (post_id, chunk_index, chunk_text, embedding)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (post_id, chunk_index)
    DO UPDATE SET chunk_text = EXCLUDED.chunk_text, embedding = EXCLUDED.embedding
"""


def load_post_embeddings(conn, model):
    with conn.cursor() as cur:
        cur.execute(SELECT_POSTS)
        posts = cur.fetchall()

        for post_id, title in posts:
            chunks = chunk_sentences(title)
            embeddings = vectorize_chunks(model, chunks)

            for chunk_index, (chunk_text, embedding) in enumerate(
                zip(chunks, embeddings)
            ):
                cur.execute(
                    UPSERT_EMBEDDING, (post_id, chunk_index, chunk_text, embedding)
                )

    conn.commit()


if __name__ == "__main__":
    model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dimensiones
    with psycopg.connect(**DB_CONFIG) as conn:
        load_post_embeddings(conn, model)
