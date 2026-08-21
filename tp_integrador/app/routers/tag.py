from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_connection

router = APIRouter(prefix="/tags")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_tags(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM TAG ORDER BY name")
        tags = cur.fetchall()
    return templates.TemplateResponse(request, "tag/list.html", {"tags": tags})


@router.get("/new")
def new_tag_form(request: Request):
    return templates.TemplateResponse(request, "tag/form.html", {"tag": None})


@router.get("/{tag_id}/edit")
def edit_tag_form(request: Request, tag_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM TAG WHERE id = %s", (tag_id,))
        tag = cur.fetchone()
    return templates.TemplateResponse(request, "tag/form.html", {"tag": tag})


@router.post("")
def create_tag(name: str = Form(...), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO TAG (name) VALUES (%s)", (name,))
    conn.commit()
    return RedirectResponse("/tags", status_code=303)


@router.post("/{tag_id}")
def update_tag(tag_id: str, name: str = Form(...), conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("UPDATE TAG SET name = %s WHERE id = %s", (name, tag_id))
    conn.commit()
    return RedirectResponse("/tags", status_code=303)


@router.post("/{tag_id}/delete")
def delete_tag(tag_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM TAG WHERE id = %s", (tag_id,))
    conn.commit()
    return RedirectResponse("/tags", status_code=303)
