SET search_path TO public;

BEGIN;

INSERT INTO ROLE (id, name) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Admin'),
    ('22222222-2222-2222-2222-222222222222', 'User'),
    ('33333333-3333-3333-3333-333333333333', 'Moderator'),
    ('44444444-4444-4444-4444-444444444444', 'Editor');

INSERT INTO "user" (id, username, email, password_hash, created_at) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'admin_user', 'admin@grupo1.net', '$2b$12$KIXpZ0Xf8yV8T7M1a9Qe0uJkP9z8W7v6U5t4S3r2Q1p0O9n8M7l6K', NOW() - INTERVAL '30 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'alice_smith', 'alice@example.com', '$2b$12$E21J7h3n0X9T8M7L6K5J4I3H2G1F0E9D8C7B6A5Z4Y3X2W1V0U9T', NOW() - INTERVAL '20 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'bob_jones', 'bob@example.com', '$2b$12$Z9Y8X7W6V5U4T3S2R1Q0P9O8N7M6L5K4J3I2H1G0F9E8D7C6B5', NOW() - INTERVAL '15 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'charlie_brown', 'charlie@example.com', '$2b$12$M7L6K5J4I3H2G1F0E9D8C7B6A5Z4Y3X2W1V0U9T8S7R6Q5P4O3', NOW() - INTERVAL '10 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'diana_prince', 'diana@example.com', '$2b$12$Q5P4O3N2M1L0K9J8I7H6G5F4E3D2C1B0A9Z8Y7X6W5V4U3T2S1', NOW() - INTERVAL '5 days');

INSERT INTO USER_ROLE (user_id, role_id, assigned_at) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', '11111111-1111-1111-1111-111111111111', NOW() - INTERVAL '30 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', '22222222-2222-2222-2222-222222222222', NOW() - INTERVAL '20 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', '22222222-2222-2222-2222-222222222222', NOW() - INTERVAL '15 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', '33333333-3333-3333-3333-333333333333', NOW() - INTERVAL '10 days'),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', '44444444-4444-4444-4444-444444444444', NOW() - INTERVAL '5 days');

INSERT INTO CATEGORY (id, name, description) VALUES
    ('c1111111-1111-1111-1111-111111111111', 'Inteligencia Artificial', 'Contenidos sobre IA, Machine Learning y Redes Neuronales'),
    ('c2222222-2222-2222-2222-222222222222', 'Bases de Datos', 'Bases de datos relacionales, NoSQL y modelado de datos'),
    ('c3333333-3333-3333-3333-333333333333', 'Desarrollo Web', 'Frontend, Backend, APIs y frameworks modernos'),
    ('c4444444-4444-4444-4444-444444444444', 'DevOps & Cloud', 'Docker, Kubernetes, CI/CD y servicios en la nube');

INSERT INTO TAG (id, name) VALUES
    ('d1111111-1111-1111-1111-111111111111', 'PostgreSQL'),
    ('d2222222-2222-2222-2222-222222222222', 'Python'),
    ('d3333333-3333-3333-3333-333333333333', 'Docker'),
    ('d4444444-4444-4444-4444-444444444444', 'Machine Learning'),
    ('d5555555-5555-5555-5555-555555555555', 'SQL'),
    ('d6666666-6666-6666-6666-666666666666', 'FastAPI'),
    ('d7777777-7777-7777-7777-777777777777', 'LLMs');

INSERT INTO PREFERENCE (id, user_id, category_id) VALUES
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'c1111111-1111-1111-1111-111111111111'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'c2222222-2222-2222-2222-222222222222'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'c2222222-2222-2222-2222-222222222222'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'c4444444-4444-4444-4444-444444444444'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'c3333333-3333-3333-3333-333333333333');

INSERT INTO CONTENT (id, creator_id, category_id, title, content_type, created_at) VALUES
    ('b1111111-1111-1111-1111-111111111111', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'c2222222-2222-2222-2222-222222222222', 'Tutorial de PostgreSQL 16 desde Cero', 'video', NOW() - INTERVAL '12 days'),
    ('b2222222-2222-2222-2222-222222222222', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'c1111111-1111-1111-1111-111111111111', 'Introducción a Modelos de Lenguaje LLM', 'article', NOW() - INTERVAL '10 days'),
    ('b3333333-3333-3333-3333-333333333333', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'c3333333-3333-3333-3333-333333333333', 'Novedades sobre la cursada de BDIA 2026', 'post', NOW() - INTERVAL '8 days'),
    ('b4444444-4444-4444-4444-444444444444', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'c1111111-1111-1111-1111-111111111111', 'Curso Completo de Data Engineering & IA', 'course', NOW() - INTERVAL '6 days'),
    ('b5555555-5555-5555-5555-555555555555', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'c2222222-2222-2222-2222-222222222222', 'Especificación del TP Integrador BDIA', 'document', NOW() - INTERVAL '4 days'),
    ('b6666666-6666-6666-6666-666666666666', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a55', 'c4444444-4444-4444-4444-444444444444', 'Infraestructura y Despliegue en la Nube', 'photo', NOW() - INTERVAL '2 days');

INSERT INTO VIDEO (id, content_id, video_url, duration_seconds) VALUES
    (gen_random_uuid(), 'b1111111-1111-1111-1111-111111111111', 'http://localhost:9000/assets/tutorial_pg16.mp4', 3600);

INSERT INTO PHOTO (id, content_id, photo_url, height, width) VALUES
    (gen_random_uuid(), 'b6666666-6666-6666-6666-666666666666', 'http://localhost:9000/assets/infraestructura_cloud.png', 1080, 1920);

INSERT INTO ARTICLE (id, content_id, author, full_text) VALUES
    (gen_random_uuid(), 'b2222222-2222-2222-2222-222222222222', 'Alice Smith', 'Los modelos de lenguaje de gran escala (LLM) han revolucionado el procesamiento de lenguaje natural...');

INSERT INTO POST (id, content_id, is_pinned, body) VALUES
    (gen_random_uuid(), 'b3333333-3333-3333-3333-333333333333', TRUE, 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus tincidunt aliquam magna, ut consectetur ipsum tempus at. In lacus magna, pretium eget nulla non, condimentum ultricies nibh. Nullam eu ex tortor. Quisque rutrum maximus quam, quis fringilla ex accumsan semper.');

INSERT INTO COURSE (id, content_id, description, total_modules) VALUES
    (gen_random_uuid(), 'b4444444-4444-4444-4444-444444444444', 'Curso intensivo sobre diseño de bases de datos, procesamiento masivo e inteligencia artificial.', 12);

INSERT INTO DOCUMENT (id, content_id, file_format, file_size_kb) VALUES
    (gen_random_uuid(), 'b5555555-5555-5555-5555-555555555555', 'PDF', 2048);

INSERT INTO CONTENT_TAG (content_id, tag_id) VALUES
    ('b1111111-1111-1111-1111-111111111111', 'd1111111-1111-1111-1111-111111111111'),     
    ('b1111111-1111-1111-1111-111111111111', 'd5555555-5555-5555-5555-555555555555'),     
    ('b2222222-2222-2222-2222-222222222222', 'd2222222-2222-2222-2222-222222222222'),     
    ('b2222222-2222-2222-2222-222222222222', 'd7777777-7777-7777-7777-777777777777'),     
    ('b4444444-4444-4444-4444-444444444444', 'd4444444-4444-4444-4444-444444444444'),     
    ('b5555555-5555-5555-5555-555555555555', 'd1111111-1111-1111-1111-111111111111'),
    ('b6666666-6666-6666-6666-666666666666', 'd3333333-3333-3333-3333-333333333333'); 

INSERT INTO HISTORY (id, user_id, content_id, viewed_at) VALUES
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b1111111-1111-1111-1111-111111111111', NOW() - INTERVAL '5 days'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b2222222-2222-2222-2222-222222222222', NOW() - INTERVAL '3 days'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'b1111111-1111-1111-1111-111111111111', NOW() - INTERVAL '2 days'),
    (gen_random_uuid(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b3333333-3333-3333-3333-333333333333', NOW() - INTERVAL '1 day');

INSERT INTO SEARCH (id, user_id, query_text, searched_at) VALUES
    ('e1111111-1111-1111-1111-111111111111', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'PostgreSQL tutorial', NOW() - INTERVAL '5 days'),
    ('e2222222-2222-2222-2222-222222222222', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'inteligencia artificial', NOW() - INTERVAL '2 days');

INSERT INTO SEARCH_RESULT (search_id, content_id, rank_position) VALUES
    ('e1111111-1111-1111-1111-111111111111', 'b1111111-1111-1111-1111-111111111111', 1),
    ('e1111111-1111-1111-1111-111111111111', 'b5555555-5555-5555-5555-555555555555', 2),
    ('e2222222-2222-2222-2222-222222222222', 'b2222222-2222-2222-2222-222222222222', 1),
    ('e2222222-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', 2);

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f1111111-1111-1111-1111-111111111111', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b1111111-1111-1111-1111-111111111111', 'view', NOW() - INTERVAL '5 days');

INSERT INTO "view" (id, interaction_id, duration_seconds) VALUES
    (gen_random_uuid(), 'f1111111-1111-1111-1111-111111111111', 1800);

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f2222222-2222-2222-2222-222222222222', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b2222222-2222-2222-2222-222222222222', 'reaction', NOW() - INTERVAL '3 days');

INSERT INTO REACTION (id, interaction_id, reaction_type) VALUES
    (gen_random_uuid(), 'f2222222-2222-2222-2222-222222222222', 'like');

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f3333333-3333-3333-3333-333333333333', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33', 'b2222222-2222-2222-2222-222222222222', 'share', NOW() - INTERVAL '2 days');

INSERT INTO SHARE (id, interaction_id, platform) VALUES
    (gen_random_uuid(), 'f3333333-3333-3333-3333-333333333333', 'LinkedIn');

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f4444444-4444-4444-4444-444444444444', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b3333333-3333-3333-3333-333333333333', 'report', NOW() - INTERVAL '1 day');

INSERT INTO REPORT (id, interaction_id, description, reason, status) VALUES
    (gen_random_uuid(), 'f4444444-4444-4444-4444-444444444444', 'El anuncio contiene un enlace roto', 'other', 'pending');

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f5555555-5555-5555-5555-555555555555', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'b5555555-5555-5555-5555-555555555555', 'management', NOW() - INTERVAL '4 days');

INSERT INTO MANAGEMENT (id, interaction_id, action_type) VALUES
    (gen_random_uuid(), 'f5555555-5555-5555-5555-555555555555', 'create');

INSERT INTO INTERACTION (id, user_id, content_id, interaction_type, created_at) VALUES
    ('f6666666-6666-6666-6666-666666666666', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b1111111-1111-1111-1111-111111111111', 'management', NOW() - INTERVAL '12 days'),
    ('f7777777-7777-7777-7777-777777777777', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22', 'b2222222-2222-2222-2222-222222222222', 'management', NOW() - INTERVAL '10 days'),
    ('f8888888-8888-8888-8888-888888888888', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b3333333-3333-3333-3333-333333333333', 'management', NOW() - INTERVAL '8 days'),
    ('f9999999-9999-9999-9999-999999999999', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a44', 'b4444444-4444-4444-4444-444444444444', 'management', NOW() - INTERVAL '6 days');

INSERT INTO MANAGEMENT (id, interaction_id, action_type) VALUES
    (gen_random_uuid(), 'f6666666-6666-6666-6666-666666666666', 'create'),
    (gen_random_uuid(), 'f7777777-7777-7777-7777-777777777777', 'create'),
    (gen_random_uuid(), 'f8888888-8888-8888-8888-888888888888', 'create'),
    (gen_random_uuid(), 'f9999999-9999-9999-9999-999999999999', 'create');

COMMIT;
