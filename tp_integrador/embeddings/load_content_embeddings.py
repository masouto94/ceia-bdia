import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import tuple_row
from sentence_transformers import SentenceTransformer

from embeddings.create_embeddings import chunk_sentences, vectorize_chunks

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_CONFIG = {
    "host": os.environ["PGHOST"],
    "port": os.environ["PGPORT"],
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
}

SELECT_CONTENT = """
    SELECT
        content.id AS content_id,
        content.title,
        post.body,
        article.full_text,
        COALESCE(course.description, video.description, photo.description) AS description
    FROM CONTENT content
    LEFT JOIN POST post ON post.content_id = content.id
    LEFT JOIN ARTICLE article ON article.content_id = content.id
    LEFT JOIN COURSE course ON course.content_id = content.id
    LEFT JOIN VIDEO video ON video.content_id = content.id
    LEFT JOIN PHOTO photo ON photo.content_id = content.id
"""

UPSERT_EMBEDDING = """
    INSERT INTO CONTENT_EMBEDDING (content_id, source_type, chunk_index, chunk_text, embedding)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (content_id, source_type, chunk_index)
    DO UPDATE SET chunk_text = EXCLUDED.chunk_text, embedding = EXCLUDED.embedding
"""


def load_content_embeddings(conn, model, content_id=None):
    select_sql = SELECT_CONTENT
    params = ()
    if content_id is not None:
        select_sql += " WHERE content.id = %s"
        params = (content_id,)

    with conn.cursor(row_factory=tuple_row) as read_cur:
        read_cur.execute(select_sql, params)
        rows = read_cur.fetchall()

    with conn.cursor() as write_cur:
        for row_content_id, title, body, full_text, description in rows:
            sources = (
                ("title", title),
                ("body", body),
                ("full_text", full_text),
                ("description", description),
            )
            for source_type, text in sources:
                if not text:
                    continue

                chunks = chunk_sentences(text)
                embeddings = vectorize_chunks(model, chunks)

                for chunk_index, (chunk_text, embedding) in enumerate(
                    zip(chunks, embeddings)
                ):
                    write_cur.execute(
                        UPSERT_EMBEDDING,
                        (
                            row_content_id,
                            source_type,
                            chunk_index,
                            chunk_text,
                            embedding,
                        ),
                    )

    conn.commit()


if __name__ == "__main__":
    model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dimensiones
    with psycopg.connect(**DB_CONFIG) as conn:
        load_content_embeddings(conn, model)
