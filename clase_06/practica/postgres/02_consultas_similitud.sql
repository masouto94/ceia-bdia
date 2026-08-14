-- Objetivo: consultar por similitud vectorial y comparar contra búsqueda literal (Paso 3).
-- Requiere / entradas: fragmentos ya cargados con embedding (scripts/cargar_documentos.py).
-- Produce / modifica: no modifica datos; sólo consultas de lectura.
-- Resultado esperado: rankings por distancia coseno, con y sin filtro relacional.
-- Guía: la búsqueda vectorial amplía SQL con un nuevo criterio de ordenamiento;
--   no reemplaza JOIN, WHERE ni la búsqueda por coincidencia de texto.

-- 1) Ranking simple: los 5 fragmentos más parecidos al fragmento id = 1.
--    Se usa el propio embedding de un fragmento ya cargado como "vector de consulta",
--    para poder probar esto directamente en psql sin necesitar una aplicación externa.
SELECT
    f.id,
    f.contenido,
    f.pagina,
    f.embedding <=> (SELECT embedding FROM fragmentos WHERE id = 1) AS distancia
FROM fragmentos f
ORDER BY distancia
LIMIT 5;

-- 2) Consulta híbrida: similitud + filtro relacional + JOIN (equivalente al Paso 3 del mockup).
--    Reemplazar el id de referencia (1) y la categoría según lo que se quiera probar.
SELECT
    f.id,
    f.contenido,
    f.pagina,
    d.titulo,
    f.embedding <=> (SELECT embedding FROM fragmentos WHERE id = 1) AS distancia
FROM fragmentos f
JOIN documentos d ON d.id = f.documento_id
WHERE d.activo = TRUE
  AND d.categoria = 'arquitectura_medallion'
ORDER BY distancia
LIMIT 5;

-- 3) Búsqueda literal equivalente, para comparar contra los rankings anteriores.
--    Sólo encuentra filas que contienen exactamente la palabra buscada.
SELECT id, contenido
FROM fragmentos
WHERE contenido ILIKE '%duplicad%'
LIMIT 5;

-- El punto pedagógico: (1) y (2) devuelven un ranking por cercanía de significado;
-- (3) devuelve coincidencia literal de una palabra. Para ver la diferencia con las
-- 25 consultas de prueba del dataset, usar scripts/comparar_busqueda.py, que ejecuta
-- ambas búsquedas para la misma pregunta en lenguaje natural.
