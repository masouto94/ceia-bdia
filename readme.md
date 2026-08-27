# Bases de Datos para Inteligencia Artificial

Repositorio de la materia **Bases de Datos para Inteligencia Artificial**, correspondiente a la **Especialización en Inteligencia Artificial (CEIA)** de la **Facultad de Ingeniería de la Universidad de Buenos Aires**.

La materia propone una introducción integral a las tecnologías de gestión de datos utilizadas en sistemas de Inteligencia Artificial, Ciencia de Datos y aplicaciones modernas basadas en datos.

A lo largo del curso se trabajan conceptos de bases de datos relacionales, lenguaje SQL, modelado de datos, bases NoSQL, arquitecturas modernas de datos, bases vectoriales, seguridad, escalabilidad y buenas prácticas para el diseño de soluciones de datos aplicadas a IA.

---

## Objetivos de la materia

El objetivo general de la materia es brindar herramientas conceptuales y prácticas para que los estudiantes puedan diseñar, consultar, administrar y seleccionar soluciones de almacenamiento de datos adecuadas para proyectos de Inteligencia Artificial.

En particular, se busca que los estudiantes puedan:

* Comprender el rol de las bases de datos en proyectos de IA y Ciencia de Datos.
* Diferenciar modelos de datos relacionales, NoSQL, vectoriales y especializados.
* Diseñar modelos conceptuales, lógicos y físicos de datos.
* Utilizar SQL para crear, consultar y manipular datos.
* Aplicar principios de diseño relacional, normalización e integridad referencial.
* Analizar criterios de selección tecnológica según el problema a resolver.
* Comprender arquitecturas modernas como Data Warehouse, Data Lake y Lakehouse.
* Utilizar bases vectoriales para búsqueda semántica y aplicaciones RAG.
* Reconocer aspectos de seguridad, aislamiento de datos y escalabilidad en sistemas conectados a modelos de IA.

---

## Contenidos

La materia se organiza en **8 clases de 3 horas**.

### Clase 1 — Introducción a Bases de Datos para Inteligencia Artificial

Conceptos de dato, información y conocimiento. Sistemas gestores de bases de datos. Evolución histórica de las bases de datos. Tipos de datos estructurados, semiestructurados y no estructurados. Clasificación de bases de datos. Rol de las bases de datos en proyectos de IA.

### Clase 2 — Modelado de Datos y Lenguaje SQL

Modelado conceptual, lógico y físico. Modelo Entidad-Relación. Entidades, atributos, relaciones, cardinalidades y restricciones. UML aplicado al modelado de datos. Introducción a SQL y sus principales familias de comandos.

### Clase 3 — Diseño de Bases de Datos Relacionales

Principios de diseño relacional. Integridad referencial. Claves primarias y foráneas. Normalización. Consultas SQL con JOINs, subconsultas y agregaciones. Índices, vistas, vistas materializadas y uso de JSON/JSONB en PostgreSQL.

### Clase 4 — Bases de Datos NoSQL

Fundamentos del paradigma NoSQL. Bases documentales, clave-valor, columnares y de grafos. Casos de uso, criterios de selección y comparación entre SQL y NoSQL. Introducción a consultas en sistemas NoSQL.

### Clase 5 — Arquitecturas Modernas de Datos

Computación en la nube aplicada a bases de datos. Arquitecturas híbridas. Data Warehouse, Data Lake y Data Lakehouse. Arquitectura Medallion. Introducción al paradigma Big Data.

### Clase 6 — Bases de Datos Vectoriales, Concurrencia y Escalabilidad

Embeddings, bases de datos vectoriales, índices vectoriales y búsqueda por similitud. Aplicaciones en IA generativa y sistemas RAG. Transacciones, propiedades ACID, concurrencia, recuperabilidad, replicación, particionamiento y escalabilidad.

### Clase 7 — Seguridad Aplicada, Tecnologías Especializadas y Buenas Prácticas

Arquitecturas multi-tenant. Row Level Security en PostgreSQL. Aislamiento de datos en aplicaciones conectadas a modelos de lenguaje. Patrones seguros para text-to-SQL y RAG. Riesgos de prompt injection y filtración de datos entre tenants. Buenas prácticas de modelado, diseño y optimización.

### Clase 8 — Repaso, Caso Práctico Integrador y Consultas

Repaso general de contenidos. Resolución de un caso práctico integrador. Validación de avances y consultas del trabajo práctico final.

---

## Estructura del repositorio

```text
.
├── programa/
│   └── Programa Materia Bases de Datos para Inteligencia Artificial.pdf
│
├── clase_01/
│   └── Presentacion.pdf
│
├── clase_02/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_03/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_04/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_05/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_06/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_07/
│   ├── Presentacion.pdf
│   └── practica/
│
├── clase_08/
│   ├── Presentacion.pdf
│   └── practica/
│
│
├── tp_final/
│
└── README.md
```

---

## Actividades prácticas

Durante la materia se desarrollan actividades prácticas orientadas a aplicar los conceptos vistos en clase.

Entre las actividades previstas se incluyen:

* Identificación de tipos de datos y tecnologías apropiadas para distintos casos de IA.
* Construcción de diagramas Entidad-Relación.
* Creación de tablas, inserción de datos y consultas SQL en PostgreSQL.
* Normalización de datasets desnormalizados.
* Consultas SQL intermedias con JOINs, GROUP BY y funciones de ventana.
* Creación de índices y comparación de tiempos de ejecución.
* Modelado comparativo de un caso de uso en SQL y MongoDB.
* Diseño de pipelines de datos por capas.
* Generación de embeddings y búsqueda por similitud.
* Implementación de políticas de Row Level Security.
* Simulación de acceso a datos desde aplicaciones conectadas a modelos de lenguaje.

---

## Trabajo práctico final

La carpeta `tp_final/` contiene la consigna, recursos y pautas para el trabajo práctico integrador de la materia.

El trabajo final consiste en el diseño de una solución de datos para un escenario vinculado con Inteligencia Artificial.

La propuesta deberá contemplar:

* Modelado de datos.
* Selección de tecnologías.
* Diseño de arquitectura.
* Criterios de seguridad.
* Escalabilidad.
* Justificación de las decisiones adoptadas.

La entrega final incluye la presentación y defensa del caso desarrollado.

---

## Tecnologías de referencia

A lo largo de la materia se mencionan y utilizan distintas tecnologías asociadas al ecosistema de datos e IA, entre ellas:

* PostgreSQL
* MongoDB
* Redis
* Neo4j
* Cassandra
* pgvector
* Chroma
* Pinecone
* Weaviate
* Herramientas de modelado de datos
* Servicios cloud de bases de datos
* Arquitecturas Data Warehouse, Data Lake y Lakehouse

---

## Modalidad

La materia combina clases teóricas con actividades prácticas. Cada encuentro busca conectar los conceptos vistos con decisiones reales de diseño, implementación y selección tecnológica en sistemas basados en datos e Inteligencia Artificial.

---

## Docente responsable

**Esp. Lic. Martín Aníbal Lacheski**
Facultad de Ingeniería — Universidad de Buenos Aires
Especialización en Inteligencia Artificial

