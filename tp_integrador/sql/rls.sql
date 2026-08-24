-- =============================================================================
-- Row-Level Security: aislamiento de datos por usuario y rol
-- =============================================================================
-- Se ejecuta despues de ddl.sql y seed.sql.
--
-- ALCANCE
-- Cada usuario de la aplicacion se mapea a un rol de login de PostgreSQL con el
-- mismo nombre que su username. Las politicas usan session_user, que el motor
-- garantiza y no puede falsificarse desde SQL.
--
-- La aplicacion FastAPI sigue conectandose con el usuario propietario del
-- esquema (admin), que es superusuario y omite RLS: su comportamiento no
-- cambia. El aislamiento aqui definido aplica a las conexiones que utilizan
-- los roles creados en este archivo (psql, pgAdmin, cualquier cliente).
--
-- SEMANTICA DE ROLES
--   User       consulta el catalogo; ve unicamente sus propios datos de
--              actividad; puede publicar contenido propio.
--   Editor     ademas edita y elimina contenido ajeno.
--   Moderator  ademas accede a todas las denuncias.
--   Admin      acceso total, incluida la gestion de usuarios y roles.
--
-- Publicar contenido es capacidad de todos los roles; los roles diferencian
-- moderacion y administracion.
-- =============================================================================

SET search_path TO public;

-- -----------------------------------------------------------------------------
-- 1. Rol de aplicacion y roles de login por usuario
-- -----------------------------------------------------------------------------
-- app_user agrupa los privilegios comunes. No tiene LOGIN: se hereda.

CREATE ROLE app_user NOLOGIN;

GRANT USAGE ON SCHEMA public TO app_user;

-- Catalogo y datos operativos: lectura y escritura, acotadas luego por RLS.
GRANT SELECT, INSERT, UPDATE, DELETE ON
    CONTENT, VIDEO, PHOTO, ARTICLE, POST, COURSE, DOCUMENT,
    CONTENT_TAG, HISTORY, SEARCH, SEARCH_RESULT,
    INTERACTION, "view", REACTION, SHARE, REPORT, MANAGEMENT,
    PREFERENCE, USER_PREFERENCE
TO app_user;

-- Catalogos de referencia: solo lectura para roles no administrativos.
GRANT SELECT ON CATEGORY, TAG, ROLE, USER_ROLE, CONTENT_EMBEDDING TO app_user;

-- La tabla de usuarios se expone solo por lectura; RLS restringe las filas.
GRANT SELECT ON "user" TO app_user;

-- Un rol de login por cada usuario del seed. El nombre coincide con username.
CREATE ROLE admin_user     LOGIN PASSWORD 'demo1234' IN ROLE app_user;
CREATE ROLE alice_smith    LOGIN PASSWORD 'demo1234' IN ROLE app_user;
CREATE ROLE bob_jones      LOGIN PASSWORD 'demo1234' IN ROLE app_user;
CREATE ROLE charlie_brown  LOGIN PASSWORD 'demo1234' IN ROLE app_user;
CREATE ROLE diana_prince   LOGIN PASSWORD 'demo1234' IN ROLE app_user;

-- -----------------------------------------------------------------------------
-- 2. Funciones de contexto
-- -----------------------------------------------------------------------------
-- Resuelven la identidad y los roles del usuario conectado.
--
-- SECURITY DEFINER: se ejecutan con los privilegios del propietario, de modo
-- que puedan consultar "user", USER_ROLE y ROLE sin quedar sujetas a las
-- politicas RLS de esas tablas (lo que produciria recursion infinita).
-- STABLE permite al planificador evaluarlas una sola vez por consulta.

CREATE FUNCTION app_current_user_id() RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT id FROM "user" WHERE username = session_user;
$$;

CREATE FUNCTION app_has_role(role_name TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM USER_ROLE ur
        JOIN ROLE r ON r.id = ur.role_id
        JOIN "user" u ON u.id = ur.user_id
        WHERE u.username = session_user
          AND r.name = role_name
    );
$$;

-- Atajos de legibilidad para las politicas.
CREATE FUNCTION app_is_admin() RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$ SELECT app_has_role('Admin'); $$;

CREATE FUNCTION app_can_moderate() RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$ SELECT app_has_role('Moderator') OR app_has_role('Admin'); $$;

CREATE FUNCTION app_can_edit_any_content() RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT app_has_role('Editor') OR app_has_role('Moderator') OR app_has_role('Admin');
$$;

-- Devuelve el creador ya almacenado de un contenido. Se usa en el WITH CHECK
-- de CONTENT para distinguir "conservar la autoria" de "reasignarla".
CREATE FUNCTION app_content_creator(content_id UUID) RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT creator_id FROM CONTENT WHERE id = content_id;
$$;

GRANT EXECUTE ON FUNCTION
    app_current_user_id(), app_has_role(TEXT),
    app_is_admin(), app_can_moderate(), app_can_edit_any_content(),
    app_content_creator(UUID)
TO app_user;

-- -----------------------------------------------------------------------------
-- 3. Datos personales de actividad: aislamiento horizontal
-- -----------------------------------------------------------------------------
-- Cada usuario accede unicamente a sus propias filas. Admin puede leer todo,
-- pero WITH CHECK impide que cualquiera, incluido Admin, escriba filas a
-- nombre de otro usuario.

ALTER TABLE HISTORY ENABLE ROW LEVEL SECURITY;
ALTER TABLE HISTORY FORCE ROW LEVEL SECURITY;
CREATE POLICY history_propio ON HISTORY FOR ALL TO app_user
    USING (user_id = app_current_user_id() OR app_is_admin())
    WITH CHECK (user_id = app_current_user_id());

ALTER TABLE SEARCH ENABLE ROW LEVEL SECURITY;
ALTER TABLE SEARCH FORCE ROW LEVEL SECURITY;
CREATE POLICY search_propia ON SEARCH FOR ALL TO app_user
    USING (user_id = app_current_user_id() OR app_is_admin())
    WITH CHECK (user_id = app_current_user_id());

ALTER TABLE PREFERENCE ENABLE ROW LEVEL SECURITY;
ALTER TABLE PREFERENCE FORCE ROW LEVEL SECURITY;
CREATE POLICY preference_propia ON PREFERENCE FOR ALL TO app_user
    USING (user_id = app_current_user_id() OR app_is_admin())
    WITH CHECK (user_id = app_current_user_id());

ALTER TABLE USER_PREFERENCE ENABLE ROW LEVEL SECURITY;
ALTER TABLE USER_PREFERENCE FORCE ROW LEVEL SECURITY;
CREATE POLICY user_preference_propia ON USER_PREFERENCE FOR ALL TO app_user
    USING (user_id = app_current_user_id() OR app_is_admin())
    WITH CHECK (user_id = app_current_user_id());

-- Los resultados de busqueda siguen la visibilidad de la busqueda que los
-- origino: no son datos propios sino dependientes de SEARCH.
ALTER TABLE SEARCH_RESULT ENABLE ROW LEVEL SECURITY;
ALTER TABLE SEARCH_RESULT FORCE ROW LEVEL SECURITY;
CREATE POLICY search_result_propio ON SEARCH_RESULT FOR ALL TO app_user
    USING (
        app_is_admin()
        OR EXISTS (
            SELECT 1 FROM SEARCH s
            WHERE s.id = SEARCH_RESULT.search_id
              AND s.user_id = app_current_user_id()
        )
    );

-- -----------------------------------------------------------------------------
-- 4. Interacciones
-- -----------------------------------------------------------------------------
-- Las interacciones son actividad personal. Moderadores y administradores
-- necesitan verlas para poder resolver denuncias sobre ellas.

ALTER TABLE INTERACTION ENABLE ROW LEVEL SECURITY;
ALTER TABLE INTERACTION FORCE ROW LEVEL SECURITY;
CREATE POLICY interaction_propia ON INTERACTION FOR ALL TO app_user
    USING (user_id = app_current_user_id() OR app_can_moderate())
    WITH CHECK (user_id = app_current_user_id());

-- Los subtipos heredan la visibilidad de su interaccion padre.
ALTER TABLE "view" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "view" FORCE ROW LEVEL SECURITY;
CREATE POLICY view_por_interaccion ON "view" FOR ALL TO app_user
    USING (EXISTS (SELECT 1 FROM INTERACTION i WHERE i.id = "view".interaction_id));

ALTER TABLE REACTION ENABLE ROW LEVEL SECURITY;
ALTER TABLE REACTION FORCE ROW LEVEL SECURITY;
CREATE POLICY reaction_por_interaccion ON REACTION FOR ALL TO app_user
    USING (EXISTS (SELECT 1 FROM INTERACTION i WHERE i.id = REACTION.interaction_id));

ALTER TABLE SHARE ENABLE ROW LEVEL SECURITY;
ALTER TABLE SHARE FORCE ROW LEVEL SECURITY;
CREATE POLICY share_por_interaccion ON SHARE FOR ALL TO app_user
    USING (EXISTS (SELECT 1 FROM INTERACTION i WHERE i.id = SHARE.interaction_id));

ALTER TABLE MANAGEMENT ENABLE ROW LEVEL SECURITY;
ALTER TABLE MANAGEMENT FORCE ROW LEVEL SECURITY;
CREATE POLICY management_por_interaccion ON MANAGEMENT FOR ALL TO app_user
    USING (EXISTS (SELECT 1 FROM INTERACTION i WHERE i.id = MANAGEMENT.interaction_id));

-- -----------------------------------------------------------------------------
-- 5. Denuncias: el caso donde el rol rompe el aislamiento
-- -----------------------------------------------------------------------------
-- Una denuncia es visible para quien la emitio y para moderacion. El autor del
-- contenido denunciado no puede identificar al denunciante, lo que preserva el
-- proposito del mecanismo.

ALTER TABLE REPORT ENABLE ROW LEVEL SECURITY;
ALTER TABLE REPORT FORCE ROW LEVEL SECURITY;
CREATE POLICY report_acceso ON REPORT FOR ALL TO app_user
    USING (
        app_can_moderate()
        OR EXISTS (
            SELECT 1 FROM INTERACTION i
            WHERE i.id = REPORT.interaction_id
              AND i.user_id = app_current_user_id()
        )
    );

-- -----------------------------------------------------------------------------
-- 6. Contenido: catalogo publico, escritura restringida al creador
-- -----------------------------------------------------------------------------
-- La lectura es abierta: el catalogo es publico para todos los usuarios.
-- La escritura se limita al creador, salvo para Editor, Moderator y Admin.
-- WITH CHECK es mas estricto que USING: un moderador puede editar o eliminar
-- contenido ajeno, pero no publicar a nombre de otro usuario.

ALTER TABLE CONTENT ENABLE ROW LEVEL SECURITY;
ALTER TABLE CONTENT FORCE ROW LEVEL SECURITY;

CREATE POLICY content_lectura_publica ON CONTENT FOR SELECT TO app_user
    USING (true);

CREATE POLICY content_insercion_propia ON CONTENT FOR INSERT TO app_user
    WITH CHECK (creator_id = app_current_user_id() OR app_is_admin());

-- El WITH CHECK admite que quien modera conserve el creador original, pero no
-- que reasigne la autoria a un tercero: la fila resultante debe seguir
-- perteneciendo a quien edita o mantener el creador que ya tenia.
CREATE POLICY content_modificacion ON CONTENT FOR UPDATE TO app_user
    USING (creator_id = app_current_user_id() OR app_can_edit_any_content())
    WITH CHECK (
        creator_id = app_current_user_id()
        OR app_is_admin()
        OR (app_can_edit_any_content() AND creator_id = app_content_creator(id))
    );

CREATE POLICY content_borrado ON CONTENT FOR DELETE TO app_user
    USING (creator_id = app_current_user_id() OR app_can_edit_any_content());

-- Los subtipos siguen la visibilidad y la capacidad de escritura del contenido
-- padre: lectura publica, escritura solo si se puede escribir el CONTENT.
CREATE POLICY video_lectura ON VIDEO FOR SELECT TO app_user USING (true);
CREATE POLICY video_escritura ON VIDEO FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = VIDEO.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE VIDEO ENABLE ROW LEVEL SECURITY;
ALTER TABLE VIDEO FORCE ROW LEVEL SECURITY;

CREATE POLICY photo_lectura ON PHOTO FOR SELECT TO app_user USING (true);
CREATE POLICY photo_escritura ON PHOTO FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = PHOTO.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE PHOTO ENABLE ROW LEVEL SECURITY;
ALTER TABLE PHOTO FORCE ROW LEVEL SECURITY;

CREATE POLICY article_lectura ON ARTICLE FOR SELECT TO app_user USING (true);
CREATE POLICY article_escritura ON ARTICLE FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = ARTICLE.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE ARTICLE ENABLE ROW LEVEL SECURITY;
ALTER TABLE ARTICLE FORCE ROW LEVEL SECURITY;

CREATE POLICY post_lectura ON POST FOR SELECT TO app_user USING (true);
CREATE POLICY post_escritura ON POST FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = POST.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE POST ENABLE ROW LEVEL SECURITY;
ALTER TABLE POST FORCE ROW LEVEL SECURITY;

CREATE POLICY course_lectura ON COURSE FOR SELECT TO app_user USING (true);
CREATE POLICY course_escritura ON COURSE FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = COURSE.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE COURSE ENABLE ROW LEVEL SECURITY;
ALTER TABLE COURSE FORCE ROW LEVEL SECURITY;

CREATE POLICY document_lectura ON DOCUMENT FOR SELECT TO app_user USING (true);
CREATE POLICY document_escritura ON DOCUMENT FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = DOCUMENT.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));
ALTER TABLE DOCUMENT ENABLE ROW LEVEL SECURITY;
ALTER TABLE DOCUMENT FORCE ROW LEVEL SECURITY;

-- Las etiquetas de un contenido las administra quien puede editar ese contenido.
ALTER TABLE CONTENT_TAG ENABLE ROW LEVEL SECURITY;
ALTER TABLE CONTENT_TAG FORCE ROW LEVEL SECURITY;
CREATE POLICY content_tag_lectura ON CONTENT_TAG FOR SELECT TO app_user USING (true);
CREATE POLICY content_tag_escritura ON CONTENT_TAG FOR ALL TO app_user
    USING (EXISTS (
        SELECT 1 FROM CONTENT c WHERE c.id = CONTENT_TAG.content_id
          AND (c.creator_id = app_current_user_id() OR app_can_edit_any_content())));

-- -----------------------------------------------------------------------------
-- 7. Datos de usuario
-- -----------------------------------------------------------------------------
-- Cada usuario ve su propia fila completa. Moderadores y administradores ven
-- todas, ya que necesitan identificar autores y denunciantes.
-- password_hash no se expone a app_user por GRANT de columnas.

REVOKE SELECT ON "user" FROM app_user;
GRANT SELECT (id, username, email, created_at) ON "user" TO app_user;

ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "user" FORCE ROW LEVEL SECURITY;
CREATE POLICY user_visibilidad ON "user" FOR SELECT TO app_user
    USING (username = session_user OR app_can_moderate());

-- -----------------------------------------------------------------------------
-- 8. Gestion de roles: exclusiva de Admin
-- -----------------------------------------------------------------------------

ALTER TABLE USER_ROLE ENABLE ROW LEVEL SECURITY;
ALTER TABLE USER_ROLE FORCE ROW LEVEL SECURITY;
CREATE POLICY user_role_lectura ON USER_ROLE FOR SELECT TO app_user
    USING (user_id = app_current_user_id() OR app_can_moderate());

GRANT INSERT, UPDATE, DELETE ON USER_ROLE TO app_user;
CREATE POLICY user_role_admin ON USER_ROLE FOR ALL TO app_user
    USING (app_is_admin()) WITH CHECK (app_is_admin());

-- -----------------------------------------------------------------------------
-- 9. Embeddings
-- -----------------------------------------------------------------------------
-- Derivados de contenido publico: lectura abierta, sin escritura para app_user
-- (los genera el proceso de la aplicacion, que se conecta como propietario).

ALTER TABLE CONTENT_EMBEDDING ENABLE ROW LEVEL SECURITY;
ALTER TABLE CONTENT_EMBEDDING FORCE ROW LEVEL SECURITY;
CREATE POLICY content_embedding_lectura ON CONTENT_EMBEDDING FOR SELECT TO app_user
    USING (true);
