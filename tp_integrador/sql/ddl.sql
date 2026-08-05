-- PostgreSQL DDL Script generated from der.mmd
-- Database: PostgreSQL (v13+)

-- Enable pgcrypto extension for UUID generation (if using PostgreSQL < 13)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==========================================
-- ENUM TYPES
-- ==========================================

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

CREATE TYPE report_status_enum AS ENUM (
    'pending',
    'reviewed',
    'resolved',
    'dismissed'
);

CREATE TYPE action_type_enum AS ENUM (
    'approve',
    'reject',
    'delete',
    'flag'
);

-- ==========================================
-- TABLES
-- ==========================================

-- 1. ROLE
CREATE TABLE ROLE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 2. USER ("USER" is a reserved keyword in PostgreSQL)
CREATE TABLE "user" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. USER_ROLE
CREATE TABLE USER_ROLE (
    user_id UUID NOT NULL REFERENCES "USER"(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES ROLE(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- 4. CATEGORY
CREATE TABLE CATEGORY (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- 5. TAG
CREATE TABLE TAG (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 6. PREFERENCE
CREATE TABLE PREFERENCE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "USER"(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES CATEGORY(id) ON DELETE CASCADE
);

-- 7. CONTENT
CREATE TABLE CONTENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES CATEGORY(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. CONTENT_TAG
CREATE TABLE CONTENT_TAG (
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES TAG(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, tag_id)
);

-- 9. HISTORY
CREATE TABLE HISTORY (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "USER"(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. SEARCH
CREATE TABLE SEARCH (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "USER"(id) ON DELETE CASCADE,
    query_text VARCHAR(255) NOT NULL,
    searched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. SEARCH_RESULT
CREATE TABLE SEARCH_RESULT (
    search_id UUID NOT NULL REFERENCES SEARCH(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    rank_position INT NOT NULL,
    PRIMARY KEY (search_id, content_id)
);

-- 12. INTERACTION
CREATE TABLE INTERACTION (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "USER"(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES CONTENT(id) ON DELETE CASCADE,
    interaction_type interaction_type_enum NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 13. VIEW ("VIEW" is a reserved keyword in PostgreSQL)
CREATE TABLE "view" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    duration_seconds INT NOT NULL
);

-- 14. REACTION
CREATE TABLE REACTION (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    reaction_type reaction_type_enum NOT NULL
);

-- 15. SHARE
CREATE TABLE SHARE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    platform VARCHAR(100) NOT NULL
);

-- 16. REPORT
CREATE TABLE REPORT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    reason VARCHAR(255) NOT NULL,
    status report_status_enum NOT NULL DEFAULT 'pending'
);

-- 17. MANAGEMENT
CREATE TABLE MANAGEMENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL UNIQUE REFERENCES INTERACTION(id) ON DELETE CASCADE,
    action_type action_type_enum NOT NULL
);

-- 18. VIDEO
CREATE TABLE VIDEO (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    video_url VARCHAR(255) NOT NULL,
    duration_seconds INT NOT NULL
);

-- 19. ARTICLE
CREATE TABLE ARTICLE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    author VARCHAR(100) NOT NULL,
    full_text TEXT NOT NULL
);

-- 20. POST
CREATE TABLE POST (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE
);

-- 21. COURSE
CREATE TABLE COURSE (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    description VARCHAR(255),
    total_modules INT NOT NULL
);

-- 22. DOCUMENT
CREATE TABLE DOCUMENT (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL UNIQUE REFERENCES CONTENT(id) ON DELETE CASCADE,
    file_format VARCHAR(50) NOT NULL,
    file_size_kb INT NOT NULL
);

-- ==========================================
-- INDEXES FOR FOREIGN KEYS AND SEARCHES
-- ==========================================

CREATE INDEX idx_user_role_user_id ON USER_ROLE(user_id);
CREATE INDEX idx_user_role_role_id ON USER_ROLE(role_id);
CREATE INDEX idx_preference_user_id ON PREFERENCE(user_id);
CREATE INDEX idx_preference_category_id ON PREFERENCE(category_id);
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
