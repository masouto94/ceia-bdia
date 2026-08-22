from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sentence_transformers import SentenceTransformer

from app.db import get_connection
from embeddings.load_content_embeddings import load_content_embeddings

router = APIRouter(prefix="/content")
templates = Jinja2Templates(directory="app/templates")

SUBTYPE_TABLES = {
    "video": "VIDEO",
    "photo": "PHOTO",
    "article": "ARTICLE",
    "post": "POST",
    "course": "COURSE",
    "document": "DOCUMENT",
}


def get_model():
    if not hasattr(get_model, "_instance"):
        get_model._instance = SentenceTransformer("all-MiniLM-L6-v2")
    return get_model._instance


@router.get("")
def list_content(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.title, c.content_type, cat.name AS category_name
            FROM CONTENT c
            LEFT JOIN CATEGORY cat ON cat.id = c.category_id
            ORDER BY c.created_at DESC
            """
        )
        items = cur.fetchall()
    return templates.TemplateResponse(
        request, "content/list.html", {"items": items}
    )


@router.get("/new")
def new_content_form(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM CATEGORY ORDER BY name")
        categories = cur.fetchall()
        cur.execute('SELECT id, username FROM "user" ORDER BY username')
        creators = cur.fetchall()
    return templates.TemplateResponse(
        request,
        "content/form.html",
        {"content": None, "subtype": None, "categories": categories, "creators": creators},
    )


@router.get("/{content_id}/edit")
def edit_content_form(request: Request, content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM CATEGORY ORDER BY name")
        categories = cur.fetchall()
        cur.execute('SELECT id, username FROM "user" ORDER BY username')
        creators = cur.fetchall()

        cur.execute(
            "SELECT id, title, content_type, category_id, creator_id FROM CONTENT WHERE id = %s",
            (content_id,),
        )
        content = cur.fetchone()

        subtype = None
        if content:
            table = SUBTYPE_TABLES.get(content["content_type"])
            if table:
                cur.execute(
                    f"SELECT * FROM {table} WHERE content_id = %s", (content_id,)
                )
                subtype = cur.fetchone()

    return templates.TemplateResponse(
        request,
        "content/form.html",
        {
            "content": content,
            "subtype": subtype,
            "categories": categories,
            "creators": creators,
        },
    )


def _upsert_subtype(cur, content_id, content_type, form):
    if content_type == "video":
        cur.execute(
            """
            INSERT INTO VIDEO (content_id, video_url, duration_seconds)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET video_url = EXCLUDED.video_url, duration_seconds = EXCLUDED.duration_seconds
            """,
            (content_id, form["video_url"], int(form["duration_seconds"])),
        )
    elif content_type == "photo":
        cur.execute(
            """
            INSERT INTO PHOTO (content_id, photo_url)
            VALUES (%s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET photo_url = EXCLUDED.photo_url
            """,
            (content_id, form["photo_url"]),
        )
    elif content_type == "article":
        cur.execute(
            """
            INSERT INTO ARTICLE (content_id, author, full_text)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET author = EXCLUDED.author, full_text = EXCLUDED.full_text
            """,
            (content_id, form["author"], form["full_text"]),
        )
    elif content_type == "post":
        cur.execute(
            """
            INSERT INTO POST (content_id, is_pinned, body)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET is_pinned = EXCLUDED.is_pinned, body = EXCLUDED.body
            """,
            (content_id, form.get("is_pinned") == "on", form["body"]),
        )
    elif content_type == "course":
        cur.execute(
            """
            INSERT INTO COURSE (content_id, description, total_modules)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET description = EXCLUDED.description, total_modules = EXCLUDED.total_modules
            """,
            (content_id, form.get("description") or None, int(form["total_modules"])),
        )
    elif content_type == "document":
        cur.execute(
            """
            INSERT INTO DOCUMENT (content_id, file_format, file_size_kb)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET file_format = EXCLUDED.file_format, file_size_kb = EXCLUDED.file_size_kb
            """,
            (content_id, form["file_format"], int(form["file_size_kb"])),
        )


@router.post("")
async def create_content(request: Request, conn=Depends(get_connection)):
    form = dict((await request.form()).items())

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO CONTENT (title, creator_id, content_type, category_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (form["title"], form["creator_id"], form["content_type"], form.get("category_id") or None),
        )
        content_id = cur.fetchone()["id"]
        _upsert_subtype(cur, content_id, form["content_type"], form)

    conn.commit()

    load_content_embeddings(conn, get_model(), content_id=content_id)

    return RedirectResponse("/content", status_code=303)


@router.post("/{content_id}")
async def update_content(content_id: str, request: Request, conn=Depends(get_connection)):
    form = dict((await request.form()).items())

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE CONTENT SET title = %s, category_id = %s WHERE id = %s",
            (form["title"], form.get("category_id") or None, content_id),
        )
        cur.execute("SELECT content_type FROM CONTENT WHERE id = %s", (content_id,))
        content_type = cur.fetchone()["content_type"]
        _upsert_subtype(cur, content_id, content_type, form)

    conn.commit()

    load_content_embeddings(conn, get_model(), content_id=content_id)

    return RedirectResponse("/content", status_code=303)


@router.post("/{content_id}/delete")
def delete_content(content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM CONTENT WHERE id = %s", (content_id,))
    conn.commit()
    return RedirectResponse("/content", status_code=303)
