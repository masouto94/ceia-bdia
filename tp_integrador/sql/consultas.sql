-- Consultas representativas del sistema de recomendacion de contenidos.
-- Ejecutar luego de sql/ddl.sql y sql/seed.sql.

-- 1. Filtrado: contenidos de una categoria y tipo determinados.
-- Pregunta: que contenidos de una categoria estan disponibles?
SELECT
    c.id,
    c.title,
    c.content_type,
    c.created_at
FROM CONTENT AS c
JOIN CATEGORY AS category ON category.id = c.category_id
WHERE category.name = 'Bases de Datos'
  AND c.content_type = 'video'
ORDER BY c.created_at DESC;

-- 2. Relaciones: contenidos, categoria y etiquetas.
-- Pregunta: que informacion descriptiva tiene cada contenido?
SELECT
    c.id,
    c.title,
    category.name AS category,
    STRING_AGG(tag.name, ', ' ORDER BY tag.name) AS tags
FROM CONTENT AS c
JOIN CATEGORY AS category ON category.id = c.category_id
LEFT JOIN CONTENT_TAG AS content_tag ON content_tag.content_id = c.id
LEFT JOIN TAG AS tag ON tag.id = content_tag.tag_id
GROUP BY c.id, c.title, creator.username, category.name
ORDER BY c.created_at DESC;

-- 3. Agregacion: actividad por contenido.
-- Pregunta: que contenidos concentran mas visualizaciones e interacciones?
SELECT
    c.id,
    c.title,
    COUNT(DISTINCT history.id) AS views,
    COUNT(DISTINCT interaction.id) AS interactions,
    COUNT(DISTINCT CASE WHEN interaction.interaction_type = 'reaction' THEN interaction.id END) AS reactions,
    COUNT(DISTINCT CASE WHEN interaction.interaction_type = 'share' THEN interaction.id END) AS shares
FROM CONTENT AS c
LEFT JOIN HISTORY AS history ON history.content_id = c.id
LEFT JOIN INTERACTION AS interaction ON interaction.content_id = c.id
GROUP BY c.id, c.title
ORDER BY views DESC, interactions DESC;

-- 4. Toma de decisiones: categorias preferidas de un usuario.
-- Pregunta: que contenidos se pueden recomendar primero a un usuario segun sus preferencias?
SELECT
    c.id,
    c.title,
    category.name AS category,
    c.created_at
FROM CONTENT AS c
JOIN CATEGORY AS category ON category.id = c.category_id
JOIN PREFERENCE AS preference ON preference.category_id = c.category_id
WHERE preference.user_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22'
  AND NOT EXISTS (
      SELECT 1
      FROM HISTORY AS history
      WHERE history.user_id = preference.user_id
        AND history.content_id = c.id
  )
ORDER BY c.created_at DESC;

-- 5. Optimizacion: consulta de contenidos recientes por categoria.
-- Pregunta: que contenidos recientes de una categoria se deben mostrar?
-- El filtro utiliza idx_content_category_id.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    c.id,
    c.title,
    c.content_type,
    c.created_at
FROM CONTENT AS c
WHERE c.category_id = 'c2222222-2222-2222-2222-222222222222'
ORDER BY c.created_at DESC
LIMIT 10;

-- 6. Búsqueda semántica: contenidos similares a un vector de consulta.
-- Pregunta: que fragmentos de contenido son semanticamente cercanos a una consulta?
-- :query_vector debe tener 384 dimensiones.
SELECT
    c.id,
    c.title,
    embedding.source_type,
    embedding.chunk_text,
    1 - (embedding.embedding <=> CAST(:query_vector AS vector)) AS similarity
FROM CONTENT_EMBEDDING AS embedding
JOIN CONTENT AS c ON c.id = embedding.content_id
ORDER BY embedding.embedding <=> CAST(:query_vector AS vector)
LIMIT 10;
