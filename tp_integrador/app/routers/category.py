from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_connection

router = APIRouter(prefix="/categories")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_categories(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM CATEGORY ORDER BY name")
        categories = cur.fetchall()
    return templates.TemplateResponse(
        request, "category/list.html", {"categories": categories}
    )


@router.get("/new")
def new_category_form(request: Request):
    return templates.TemplateResponse(
        request, "category/form.html", {"category": None}
    )


@router.get("/{category_id}/edit")
def edit_category_form(request: Request, category_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM CATEGORY WHERE id = %s", (category_id,))
        category = cur.fetchone()
    return templates.TemplateResponse(
        request, "category/form.html", {"category": category}
    )


@router.post("")
def create_category(
    name: str = Form(...),
    description: str = Form(""),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO CATEGORY (name, description) VALUES (%s, %s)",
            (name, description or None),
        )
    conn.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/{category_id}")
def update_category(
    category_id: str,
    name: str = Form(...),
    description: str = Form(""),
    conn=Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE CATEGORY SET name = %s, description = %s WHERE id = %s",
            (name, description or None, category_id),
        )
    conn.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/{category_id}/delete")
def delete_category(category_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM CATEGORY WHERE id = %s", (category_id,))
    conn.commit()
    return RedirectResponse("/categories", status_code=303)
