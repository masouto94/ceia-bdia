# Informe tecnico: sistema de recomendacion de contenidos

## 1. Descripcion del caso

Se propone un portal general de contenidos donde los usuarios pueden consultar materiales de distintos tipos y los creadores pueden publicarlos. El problema es encontrar informacion relevante dentro de un volumen y variedad crecientes. La solucion combina clasificacion, registro de interacciones, recomendaciones basicas y busqueda semantica.

## 2. Relevamiento de datos

Las entidades principales son usuarios, roles, contenidos, categorias, etiquetas, preferencias, historial, busquedas, resultados, interacciones y embeddings. Los contenidos pueden ser videos, fotos, articulos, publicaciones, cursos o documentos.

## 3. Clasificacion

- Estructurados: usuarios, contenidos, categorias, etiquetas y relaciones.
- Semiestructurados: atributos especificos segun el tipo de contenido.
- No estructurados: textos, cuerpos, descripciones y fragmentos.
- Operacionales: altas, bajas, modificaciones, busquedas e interacciones.
- Analiticos: conteos de visualizaciones, reacciones, compartidos y popularidad.
- Sensibles: correo, hash de contrasena, preferencias e historial.
- Trazabilidad: identificadores, fechas, busquedas e interacciones.

Los ejemplos se encuentran en `data/ejemplos/` y `sql/seed.sql`.

## 4. Modelo conceptual

El modelo conceptual se encuentra en `docs/der.mmd`. Un usuario puede crear contenidos mediante la referencia `creator_id` y realizar busquedas e interacciones. Cada contenido pertenece a una categoria y puede tener muchas etiquetas. Las busquedas producen resultados y los contenidos pueden tener varios fragmentos vectorizados.

## 5. Modelo logico

El modelo logico se encuentra en `docs/modelo_logico.mmd` y muestra las tablas y relaciones del esquema. Las columnas, tipos, claves primarias, claves foraneas y restricciones se definen en `sql/ddl.sql` como modelo fisico.

## 6. Normalizacion y decisiones

El modelo relacional se organiza hasta 3FN. Se separan catalogos, entidades y relaciones para evitar redundancias y anomalías. `CONTENT_TAG`, `USER_ROLE` y `RESULTADO_BUSQUEDA` resuelven relaciones muchos-a-muchos. Las tablas de tipos especificos evitan columnas nulas. `creator_id` identifica al usuario creador de cada contenido y `MANAGEMENT` registra acciones posteriores de gestion. `CONTENT_EMBEDDING` es una representacion derivada y controlada para optimizar la busqueda semantica.

## 7. Tecnologia

Se eligio PostgreSQL por sus relaciones, integridad referencial, restricciones e idoneidad para consultas SQL. pgvector permite guardar embeddings junto con los datos originales. MinIO provee almacenamiento de objetos S3-compatible para archivos binarios como fotos y videos, desacoplando los binarios del motor relacional. FastAPI ofrece una interfaz simple y Docker Compose facilita la ejecucion. Se descartaron bases NoSQL y vectoriales independientes por simplicidad y volumen reducido.

## 8. Implementacion minima

`sql/ddl.sql` crea extensiones, tipos enumerados, tablas e indices. `sql/seed.sql` inserta datos de prueba. La aplicacion FastAPI permite gestionar usuarios, categorias, etiquetas y contenidos. El proceso de embeddings genera vectores y los guarda en `CONTENT_EMBEDDING`. Los archivos binarios de ejemplo (foto y video) se cargan en MinIO mediante `setup.sh`, que usa `docker run minio/mc` sin requerir instalacion adicional.

## 9. Datos de ejemplo

Los datos permiten validar usuarios, categorias, etiquetas, contenidos especializados, busquedas, resultados e interacciones de gestion. Tambien incluyen textos suficientes para ejemplificar la generacion de embeddings.

## 10. Consultas representativas

`sql/consultas.sql` contiene filtrado, joins, agregaciones, una consulta para orientar recomendaciones, `EXPLAIN` y busqueda vectorial. Cada consulta incluye la pregunta que responde y su utilidad.

## 11. Datos semiestructurados y vectoriales

Los atributos variables se modelan mediante tablas especializadas. Los textos se dividen en fragmentos y se convierten en vectores de 384 dimensiones. Cada vector conserva `content_id`, origen, posicion, texto y fecha. La representacion vectorial no reemplaza los datos originales y debe actualizarse cuando cambia el contenido. Los archivos binarios (fotos y videos) se almacenan en MinIO; la base relacional conserva solo la URL de referencia en las tablas `PHOTO` y `VIDEO`, manteniendo la separacion entre datos estructurados y no estructurados.

## 12. Arquitectura

La arquitectura simple se documenta en `docs/arquitectura.md`. FastAPI recibe datos, PostgreSQL conserva el almacenamiento operacional, MinIO almacena los binarios y pgvector resuelve similitud. El proceso Python prepara datos para IA. No se incorpora un Data Warehouse ni un Data Lake por el alcance academico.

## 13. Seguridad

La implementacion es una prueba academica y no incluye autenticacion ni un sistema completo de autorizacion. Todos los contenidos se consideran parte del mismo espacio de la plataforma y no se distinguen contenidos publicos y privados. La estrategia se documenta como una propuesta minima para identificar los riesgos del modelo.

Se consideran dos perfiles conceptuales: **usuario consumidor** (consulta contenidos, realiza busquedas y registra interacciones) y **usuario creador** (publica y modifica contenidos). Las tablas `ROLE` y `USER_ROLE` se conservan para representar perfiles, aunque los permisos no se aplican actualmente desde la API.

Se consideran datos sensibles o de acceso restringido: correo electronico, hash de contrasena, historial de visualizaciones, busquedas, preferencias, reacciones y compartidos. La contrasena no debe almacenarse en texto plano; en una implementacion real se recomienda un algoritmo de hashing adaptativo como Argon2 o bcrypt y nunca exponer `password_hash` en las respuestas.

En una version futura, el acceso podria organizarse asi: consumidores con lectura de contenidos y creacion de sus propias interacciones; creadores con lectura y modificacion de los contenidos que crean; administradores con gestion general de usuarios, roles y contenidos. La base podria reforzar estas reglas mediante roles de PostgreSQL, vistas controladas o Row-Level Security. Esto no forma parte de la implementacion minima.

## 14. Escalabilidad y rendimiento

Las tablas que crecerian mas en una plataforma real serian `HISTORY` (por cada visualizacion), `INTERACTION` (por cada accion), `SEARCH`, `SEARCH_RESULT` y `CONTENT_EMBEDDING` (por cada fragmento vectorizado). Los datos de catalogo, como categorias, etiquetas y roles, crecerian mucho menos.

El esquema incluye indices sobre claves foraneas y columnas utilizadas para relacionar usuarios, contenidos, categorias, etiquetas, busquedas e interacciones, ademas de un indice HNSW sobre `CONTENT_EMBEDDING.embedding` para acelerar la similitud coseno. Los indices mejoran la lectura, pero aumentan el espacio utilizado y el costo de escritura, por lo que deberian revisarse mediante planes `EXPLAIN` y metricas reales.

Las consultas mas sensibles al crecimiento serian la busqueda semantica, el historial de un usuario ordenado por fecha, el conteo de interacciones por contenido, los contenidos recomendados por categoria y la recuperacion de los contenidos mas recientes (ver `sql/consultas.sql`).

Si aumentaran los datos o usuarios, se podrian aplicar estas estrategias: particionar `HISTORY`, `INTERACTION` y `SEARCH` por fecha; precalcular metricas de popularidad; crear vistas materializadas para indicadores frecuentes; utilizar cache para contenidos y recomendaciones repetidas; procesar embeddings de manera asincronica; separar cargas analiticas de las operaciones transaccionales; agregar replicas de lectura. Mantener todo en PostgreSQL simplifica la operacion y conserva la consistencia entre datos relacionales y embeddings, a costa de concentrar las cargas en un unico motor y limitar la escalabilidad horizontal. Para el alcance del trabajo, ese compromiso es aceptable.

## 15. Conclusiones

PostgreSQL con pgvector permite resolver el caso con una arquitectura compacta, consistente y suficientemente expresiva. MinIO desacopla el almacenamiento de binarios del motor relacional, siguiendo el patron habitual de separar datos estructurados y archivos. El modelo distingue datos operacionales, textos y representaciones vectoriales, y deja documentadas las extensiones necesarias para una plataforma de mayor escala.
