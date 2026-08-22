import hashlib

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_connection

router = APIRouter(prefix="/users")
templates = Jinja2Templates(directory="app/templates")


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


@router.get("")
def list_users(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, created_at FROM \"user\" ORDER BY username"
        )
        users = cur.fetchall()
    return templates.TemplateResponse(request, "user/list.html", {"users": users})


from app.preferences import get_user_preference, set_user_preference


@router.get("/new")
def new_user_form(request: Request):
    return templates.TemplateResponse(
        request, "user/form.html", {"user": None, "preferences": {}}
    )


@router.get("/{user_id}/edit")
def edit_user_form(request: Request, user_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email FROM \"user\" WHERE id = %s", (user_id,)
        )
        user = cur.fetchone()
    pref = get_user_preference(conn, user_id)
    return templates.TemplateResponse(
        request, "user/form.html", {"user": user, "preferences": pref}
    )


@router.post("")
def create_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    max_results: int = Form(10),
    theme: str = Form("light"),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            'INSERT INTO "user" (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id',
            (username, email, hash_password(password)),
        )
        user_id = cur.fetchone()["id"]
        set_user_preference(
            conn,
            user_id,
            {"result_list": {"max_results": max_results}, "ui": {"theme": theme}},
        )
    conn.commit()
    return RedirectResponse("/users", status_code=303)


@router.post("/{user_id}")
def update_user(
    user_id: str,
    username: str = Form(...),
    email: str = Form(...),
    max_results: int = Form(10),
    theme: str = Form("light"),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE "user" SET username = %s, email = %s WHERE id = %s',
            (username, email, user_id),
        )
        set_user_preference(
            conn,
            user_id,
            {"result_list": {"max_results": max_results}, "ui": {"theme": theme}},
        )
    conn.commit()
    return RedirectResponse("/users", status_code=303)


@router.post("/{user_id}/delete")
def delete_user(user_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute('DELETE FROM "user" WHERE id = %s', (user_id,))
    conn.commit()
    return RedirectResponse("/users", status_code=303)
