# Clase 06 — Bases de datos vectoriales y pgvector

Introducción a embeddings, búsqueda por similitud y bases de datos vectoriales, sentando la base técnica para RAG (Retrieval-Augmented Generation).

## Temas vistos

- Extensión `pgvector` en PostgreSQL: tipo de dato `vector` y distancia coseno (`<=>`).
- Generación de embeddings locales con `sentence-transformers`, usando el modelo `intfloat/multilingual-e5-small`.
- Índices vectoriales HNSW e IVFFlat, y comparación de planes de ejecución con y sin índice.
- Comparación entre búsqueda literal (`tsvector`) y búsqueda semántica basada en embeddings.
- Extensión del pipeline hacia RAG completo: recuperación de fragmentos relevantes + generación de respuesta con un LLM vía OpenRouter.

## Práctica

Se cargaron documentos y se fragmentaron, se generaron sus embeddings, se compararon estrategias de búsqueda (literal vs. semántica) y se construyó una interfaz web (Next.js) con una demo de recuperación semántica y RAG.
