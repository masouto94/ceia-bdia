#!/bin/bash
# =============================================================================
# Verificacion de las politicas de Row-Level Security definidas en sql/rls.sql
#
# Inspecciona la configuracion del esquema y luego ejercita el aislamiento
# abriendo una conexion real por cada usuario. Las conexiones separadas son
# necesarias porque las politicas se apoyan en session_user, que no cambia
# con SET ROLE.
#
# Requiere los contenedores levantados:
#   ./rls_check.sh
#
# Devuelve codigo de salida 0 si todas las verificaciones pasan.
# =============================================================================
set -u

# cd "$(dirname "$0")/.."

PASS=0
FAIL=0
BOB_UUID='a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33'
ALICE_UUID='a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22'

as_user() {
    local user="$1"; shift
    docker compose exec -T -e PGPASSWORD=demo1234 db \
        psql -U "$user" -h localhost -d grupo1 -t -A -c "$1" 2>&1 | tr -d '\r'
}

as_owner() {
    docker compose exec -T db psql -U admin -d grupo1 -t -A -c "$1" 2>&1 | tr -d '\r'
}

check() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        printf '  [OK]   %s\n' "$desc"
        PASS=$((PASS + 1))
    else
        printf '  [FALLA] %s\n         esperado: %s\n         obtenido: %s\n' \
            "$desc" "$expected" "$actual"
        FAIL=$((FAIL + 1))
    fi
}

check_contains() {
    local desc="$1" needle="$2" actual="$3"
    case "$actual" in
        *"$needle"*)
            printf '  [OK]   %s\n' "$desc"
            PASS=$((PASS + 1)) ;;
        *)
            printf '  [FALLA] %s\n         esperaba que contuviera: %s\n         obtenido: %s\n' \
                "$desc" "$needle" "$actual"
            FAIL=$((FAIL + 1)) ;;
    esac
}

visible() {
    as_user "$1" "SELECT (SELECT count(*) FROM $2);"
}

echo '================================================================'
echo ' 1. CONFIGURACION DEL ESQUEMA'
echo '================================================================'

# RLS debe estar activo y forzado. FORCE alcanza al propietario de la tabla;
# un superusuario lo omite igualmente, y por eso la aplicacion no se ve afectada.
SIN_FORCE=$(as_owner "SELECT count(*) FROM pg_class WHERE relkind='r' AND relnamespace='public'::regnamespace AND relrowsecurity AND NOT relforcerowsecurity;")
check "todas las tablas con RLS lo tienen forzado" "0" "$SIN_FORCE"

CON_RLS=$(as_owner "SELECT count(*) FROM pg_class WHERE relkind='r' AND relnamespace='public'::regnamespace AND relrowsecurity;")
check "22 tablas bajo RLS" "22" "$CON_RLS"

SIN_POLITICA=$(as_owner "SELECT count(*) FROM pg_class c WHERE c.relkind='r' AND c.relnamespace='public'::regnamespace AND c.relrowsecurity AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid);")
check "ninguna tabla con RLS quedo sin politicas" "0" "$SIN_POLITICA"

# Cada usuario de la aplicacion debe tener su rol de login, sin privilegios
# que le permitan eludir el aislamiento.
SIN_ROL=$(as_owner "SELECT count(*) FROM \"user\" u WHERE NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname=u.username AND r.rolcanlogin);")
check "todos los usuarios tienen rol de login" "0" "$SIN_ROL"

NO_HEREDA=$(as_owner "SELECT count(*) FROM \"user\" u JOIN pg_roles r ON r.rolname=u.username WHERE NOT pg_has_role(r.rolname,'app_user','MEMBER');")
check "todos heredan de app_user" "0" "$NO_HEREDA"

PRIVILEGIADOS=$(as_owner "SELECT count(*) FROM \"user\" u JOIN pg_roles r ON r.rolname=u.username WHERE r.rolsuper OR r.rolbypassrls;")
check "ningun rol de usuario omite RLS" "0" "$PRIVILEGIADOS"

# password_hash no debe figurar entre las columnas concedidas a app_user.
HASH_EXPUESTO=$(as_owner "SELECT count(*) FROM information_schema.column_privileges WHERE table_name='user' AND grantee='app_user' AND column_name='password_hash';")
check "password_hash no se concede a app_user" "0" "$HASH_EXPUESTO"

echo ''
echo '================================================================'
echo ' 2. AISLAMIENTO HORIZONTAL'
echo '================================================================'

check "alice_smith ve solo su historial"        "2" "$(visible alice_smith HISTORY)"
check "bob_jones ve solo su historial"          "1" "$(visible bob_jones HISTORY)"
check "diana_prince no tiene historial"         "0" "$(visible diana_prince HISTORY)"
check "admin_user ve todo el historial"         "4" "$(visible admin_user HISTORY)"

check "alice_smith ve solo sus busquedas"       "1" "$(visible alice_smith SEARCH)"
check "charlie_brown no tiene busquedas"        "0" "$(visible charlie_brown SEARCH)"
check "admin_user ve todas las busquedas"       "2" "$(visible admin_user SEARCH)"

check "alice_smith no ve denuncias ajenas"      "0" "$(visible alice_smith REPORT)"
check "charlie_brown modera: ve la denuncia"    "1" "$(visible charlie_brown REPORT)"

check "alice_smith ve solo su usuario"          "1" "$(as_user alice_smith 'SELECT count(*) FROM "user";')"
check "charlie_brown modera: ve los usuarios"   "5" "$(as_user charlie_brown 'SELECT count(*) FROM "user";')"

echo ''
echo '  Catalogo publico (no se aisla):'
check "alice_smith ve todo el contenido"        "6" "$(visible alice_smith CONTENT)"
check "bob_jones ve todo el contenido"          "6" "$(visible bob_jones CONTENT)"

echo ''
echo '================================================================'
echo ' 3. CONTEXTO DE IDENTIDAD'
echo '================================================================'

check "alice_smith resuelve su id"     "t"  "$(as_user alice_smith 'SELECT app_current_user_id() IS NOT NULL;')"
check "alice_smith no es admin"        "f" "$(as_user alice_smith "SELECT app_has_role('Admin');")"
check "alice_smith no edita ajeno"     "f" "$(as_user alice_smith 'SELECT app_can_edit_any_content();')"
check "charlie_brown es moderador"     "t"  "$(as_user charlie_brown "SELECT app_has_role('Moderator');")"
check "diana_prince edita ajeno"       "t"  "$(as_user diana_prince 'SELECT app_can_edit_any_content();')"
check "admin_user es admin"            "t"  "$(as_user admin_user "SELECT app_has_role('Admin');")"

echo ''
echo '================================================================'
echo ' 4. OPERACIONES QUE DEBEN FALLAR'
echo '================================================================'

check_contains "4.a alice no inserta historial de bob" \
    "violates row-level security policy" \
    "$(as_user alice_smith "INSERT INTO HISTORY (user_id, content_id) VALUES ('$BOB_UUID', (SELECT id FROM CONTENT LIMIT 1));")"

check_contains "4.b alice no publica como bob" \
    "violates row-level security policy" \
    "$(as_user alice_smith "INSERT INTO CONTENT (creator_id, category_id, title, content_type) SELECT '$BOB_UUID', id, 'Suplantacion', 'post' FROM CATEGORY LIMIT 1;")"

check_contains "4.c alice no lee password_hash" \
    "permission denied" \
    "$(as_user alice_smith 'SELECT password_hash FROM "user";')"

check "4.d bob (User) no modifica contenido ajeno" "UPDATE 0" \
    "$(as_user bob_jones "UPDATE CONTENT SET title = 'Modificado' WHERE creator_id <> coalesce(app_current_user_id(), '00000000-0000-0000-0000-000000000000');")"

check "4.e charlie (Moderator) no altera roles" "DELETE 0" \
    "$(as_user charlie_brown 'DELETE FROM USER_ROLE;')"

check_contains "4.f charlie no reasigna autoria ajena" \
    "violates row-level security policy" \
    "$(as_user charlie_brown "UPDATE CONTENT SET creator_id = '$ALICE_UUID' WHERE creator_id <> app_current_user_id();")"

echo ''
echo '================================================================'
echo ' 5. OPERACIONES QUE DEBEN FUNCIONAR'
echo '================================================================'

check "5.a alice registra busqueda propia" "INSERT 0 1" \
    "$(as_user alice_smith "INSERT INTO SEARCH (user_id, query_text) VALUES (app_current_user_id(), 'consulta de verificacion');")"

check "5.b diana publica contenido propio" "INSERT 0 1" \
    "$(as_user diana_prince "INSERT INTO CONTENT (creator_id, category_id, title, content_type) SELECT app_current_user_id(), id, 'Contenido de verificacion', 'post' FROM CATEGORY LIMIT 1;")"

check_contains "5.c charlie modera contenido ajeno" "UPDATE" \
    "$(as_user charlie_brown 'UPDATE CONTENT SET title = title WHERE creator_id <> app_current_user_id();')"

echo ''
echo '  Limpieza de los datos creados por la verificacion:'
as_owner "DELETE FROM SEARCH WHERE query_text = 'consulta de verificacion';" > /dev/null
as_owner "DELETE FROM CONTENT WHERE title = 'Contenido de verificacion';" > /dev/null
echo '  hecho.'

echo ''
echo '================================================================'
echo ' 6. LA APLICACION CONSERVA ACCESO COMPLETO'
echo '================================================================'

check "admin es superusuario"           "t" "$(as_owner "SELECT rolsuper FROM pg_roles WHERE rolname = 'admin';")"
check "admin ve todo el historial"      "4" "$(as_owner 'SELECT count(*) FROM HISTORY;')"
check "admin ve todas las busquedas"    "2" "$(as_owner 'SELECT count(*) FROM SEARCH;')"
check "admin ve todas las denuncias"    "1" "$(as_owner 'SELECT count(*) FROM REPORT;')"

echo ''
echo '================================================================'
printf ' RESULTADO: %d correctas, %d fallidas\n' "$PASS" "$FAIL"
echo '================================================================'

[ "$FAIL" -eq 0 ]
