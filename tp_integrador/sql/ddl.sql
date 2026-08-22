CREATE SCHEMA IF NOT EXISTS public;
SET search_path TO public;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TYPE interaction_type_enum AS ENUM (
    'view',
    'reaction',
    'share',
    'report',
    'management'
);

CREATE TYPE reaction_type_enum AS ENUM (
    'like',
    'dislike',
    'love',
    'laugh',
    'sad',
    'angry'
);

CREATE TYPE report_reason_enum AS ENUM (
    'spam',
    'inappropriate',
    'copyright',
    'other'
);

CREATE TYPE report_status_enum AS ENUM (
    'pending',
    'reviewed',
    'resolved',
    'dismissed'
);

CREATE TYPE action_type_enum AS ENUM (
    'create',
    'edit',
    'delete'
);

CREATE TYPE embedding_source_enum AS ENUM (
    'title',
    'body',
    'full_text',
    'description'
);

CREATE TABLE ROLE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE "user" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE USER_ROLE (
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES ROLE(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE CATEGORY (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE TAG (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE PREFERENCE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES CATEGORY(id) ON DELETE CASCADE
);

CREATE TABLE CONTENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID NOT NULL REFERENCES "user"(id) ON DELETE RESTRICT,
    category_id UUID NOT NULL REFERENCES CATEGORY(id) ON DELETE RESTRICT,
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CONTENT_TAG (
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES TAG(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, tag_id)
);

CREATE TABLE HISTORY (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE SEARCH (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    query_text VARCHAR(255) NOT NULL,
    searched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE SEARCH_RESULT (
    search_id UUID NOT NULL REFERENCES SEARCH(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    rank_position INT NOT NULL,
    PRIMARY KEY (search_id, content_id)
);

CREATE TABLE INTERACTION (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    interaction_type interaction_type_enum NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "view" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    duration_seconds INT NOT NULL
);

CREATE TABLE REACTION (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    reaction_type reaction_type_enum NOT NULL
);

CREATE TABLE SHARE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL
);

CREATE TABLE REPORT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    description VARCHAR(255) NOT NULL,
    reason report_reason_enum NOT NULL DEFAULT 'spam',
    status report_status_enum NOT NULL DEFAULT 'pending'
);

CREATE TABLE MANAGEMENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    action_type action_type_enum NOT NULL
);

CREATE TABLE VIDEO (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    video_url VARCHAR(255) NOT NULL,
    duration_seconds INT NOT NULL
);

CREATE TABLE PHOTO (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    photo_url VARCHAR(255) NOT NULL,
    height INT NOT NULL,
    width INT NOT NULL
);

CREATE TABLE ARTICLE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    author VARCHAR(100) NOT NULL,
    full_text TEXT NOT NULL
);

CREATE TABLE POST (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    body TEXT NOT NULL
);

CREATE TABLE COURSE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    description VARCHAR(255),
    total_modules INT NOT NULL
);

CREATE TABLE DOCUMENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    file_format VARCHAR(50) NOT NULL,
    file_size_kb INT NOT NULL
);

CREATE TABLE CONTENT_EMBEDDING (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    source_type embedding_source_enum NOT NULL,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (content_id, source_type, chunk_index)
);

CREATE TABLE USER_PREFERENCE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_role_user_id ON USER_ROLE(user_id);
CREATE INDEX idx_user_role_role_id ON USER_ROLE(role_id);
CREATE INDEX idx_preference_user_id ON PREFERENCE(user_id);
CREATE INDEX idx_preference_category_id ON PREFERENCE(category_id);
CREATE INDEX idx_content_creator_id ON CONTENT(creator_id);
CREATE INDEX idx_content_category_id ON CONTENT(category_id);
CREATE INDEX idx_content_tag_content_id ON CONTENT_TAG(content_id);
CREATE INDEX idx_content_tag_tag_id ON CONTENT_TAG(tag_id);
CREATE INDEX idx_history_user_id ON HISTORY(user_id);
CREATE INDEX idx_history_content_id ON HISTORY(content_id);
CREATE INDEX idx_search_user_id ON SEARCH(user_id);
CREATE INDEX idx_search_result_search_id ON SEARCH_RESULT(search_id);
CREATE INDEX idx_search_result_content_id ON SEARCH_RESULT(content_id);
CREATE INDEX idx_interaction_user_id ON INTERACTION(user_id);
CREATE INDEX idx_interaction_content_id ON INTERACTION(content_id);
CREATE INDEX idx_content_embedding_content_id ON CONTENT_EMBEDDING(content_id);
CREATE INDEX idx_content_embedding_vector ON CONTENT_EMBEDDING USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_user_preference_user_id ON USER_PREFERENCE(user_id);
