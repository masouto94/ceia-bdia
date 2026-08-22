import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from minio import Minio
from minio.error import S3Error
from PIL import Image
from sentence_transformers import SentenceTransformer
from starlette.datastructures import UploadFile

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

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.environ.get("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.environ.get("MINIO_ROOT_PASSWORD", "12345678")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "assets")


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
    )


def ensure_bucket(client: Minio, bucket_name: str = MINIO_BUCKET):
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error as exc:
        print(f"Aviso al verificar o crear el bucket {bucket_name}: {exc}")


async def _handle_photo_upload(client: Minio, photo_file, form_data):
    if isinstance(photo_file, UploadFile) and photo_file.filename:
        file_bytes = await photo_file.read()
        if len(file_bytes) > 0:
            ensure_bucket(client, MINIO_BUCKET)
            ext = os.path.splitext(photo_file.filename)[1]
            safe_name = os.path.basename(photo_file.filename)
            object_name = f"photos/{uuid.uuid4().hex[:8]}_{safe_name}"
            content_type = photo_file.content_type or "image/jpeg"
            client.put_object(
                bucket_name=MINIO_BUCKET,
                object_name=object_name,
                data=io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
            )
            photo_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_name}"
            try:
                with Image.open(io.BytesIO(file_bytes)) as img:
                    width, height = img.size
            except Exception:
                width = int(form_data.get("width") or 800)
                height = int(form_data.get("height") or 600)
            return photo_url, width, height

    photo_url = form_data.get("photo_url") or ""
    width = int(form_data.get("width") or 800)
    height = int(form_data.get("height") or 600)
    return photo_url, width, height


async def _handle_video_upload(client: Minio, video_file, form_data):
    if isinstance(video_file, UploadFile) and video_file.filename:
        file_bytes = await video_file.read()
        if len(file_bytes) > 0:
            ensure_bucket(client, MINIO_BUCKET)
            safe_name = os.path.basename(video_file.filename)
            object_name = f"videos/{uuid.uuid4().hex[:8]}_{safe_name}"
            content_type = video_file.content_type or "video/mp4"
            client.put_object(
                bucket_name=MINIO_BUCKET,
                object_name=object_name,
                data=io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
            )
            video_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_name}"
            duration = int(form_data.get("duration_seconds") or 0)
            return video_url, duration

    video_url = form_data.get("video_url") or ""
    duration = int(form_data.get("duration_seconds") or 0)
    return video_url, duration


def get_model():
    if not hasattr(get_model, "_instance"):
        get_model._instance = SentenceTransformer("all-MiniLM-L6-v2")
    return get_model._instance


@router.get("")
def list_content(request: Request, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.title, c.content_type, cat.name AS category_name,
                   p.photo_url, v.video_url
            FROM CONTENT c
            LEFT JOIN CATEGORY cat ON cat.id = c.category_id
            LEFT JOIN PHOTO p ON p.content_id = c.id
            LEFT JOIN VIDEO v ON v.content_id = c.id
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
    return templates.TemplateResponse(
        request,
        "content/form.html",
        {"content": None, "subtype": None, "categories": categories},
    )


@router.get("/{content_id}/edit")
def edit_content_form(request: Request, content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM CATEGORY ORDER BY name")
        categories = cur.fetchall()

        cur.execute(
            "SELECT id, title, content_type, category_id FROM CONTENT WHERE id = %s",
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
        },
    )


@router.get("/{content_id}/photo")
def get_content_photo(content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT photo_url FROM PHOTO WHERE content_id = %s", (content_id,))
        row = cur.fetchone()

    if not row or not row.get("photo_url"):
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    photo_url = row["photo_url"]
    prefix = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/"

    if photo_url.startswith(prefix):
        object_name = photo_url[len(prefix):]
    elif f"/{MINIO_BUCKET}/" in photo_url:
        object_name = photo_url.split(f"/{MINIO_BUCKET}/", 1)[1]
    elif photo_url.startswith("photos/"):
        object_name = photo_url
    else:
        return RedirectResponse(photo_url)

    client = get_minio_client()
    try:
        minio_response = client.get_object(MINIO_BUCKET, object_name)
        data = minio_response.read()
        content_type = minio_response.headers.get("content-type") or "image/jpeg"
        minio_response.close()
        minio_response.release_conn()
        return Response(content=data, media_type=content_type)
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"Error al obtener foto de MinIO: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{content_id}/video")
def get_content_video(content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT video_url FROM VIDEO WHERE content_id = %s", (content_id,))
        row = cur.fetchone()

    if not row or not row.get("video_url"):
        raise HTTPException(status_code=404, detail="Video no encontrado")

    video_url = row["video_url"]
    prefix = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/"

    if video_url.startswith(prefix):
        object_name = video_url[len(prefix):]
    elif f"/{MINIO_BUCKET}/" in video_url:
        object_name = video_url.split(f"/{MINIO_BUCKET}/", 1)[1]
    elif video_url.startswith("videos/"):
        object_name = video_url
    else:
        return RedirectResponse(video_url)

    client = get_minio_client()
    try:
        minio_response = client.get_object(MINIO_BUCKET, object_name)
        data = minio_response.read()
        content_type = minio_response.headers.get("content-type") or "video/mp4"
        minio_response.close()
        minio_response.release_conn()
        return Response(content=data, media_type=content_type)
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"Error al obtener video de MinIO: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


async def _upsert_subtype(cur, content_id, content_type, form):
    if content_type == "video":
        client = get_minio_client()
        video_url, duration_seconds = await _handle_video_upload(
            client, form.get("video_file"), form
        )
        cur.execute(
            """
            INSERT INTO VIDEO (content_id, video_url, duration_seconds)
            VALUES (%s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET video_url = EXCLUDED.video_url, duration_seconds = EXCLUDED.duration_seconds
            """,
            (content_id, video_url, duration_seconds),
        )
    elif content_type == "photo":
        client = get_minio_client()
        photo_url, width, height = await _handle_photo_upload(
            client, form.get("photo_file"), form
        )
        cur.execute(
            """
            INSERT INTO PHOTO (content_id, photo_url, height, width)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (content_id) DO UPDATE
            SET photo_url = EXCLUDED.photo_url, height = EXCLUDED.height, width = EXCLUDED.width
            """,
            (content_id, photo_url, height, width),
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
            INSERT INTO CONTENT (title, content_type, category_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (form["title"], form["content_type"], form.get("category_id") or None),
        )
        content_id = cur.fetchone()["id"]
        await _upsert_subtype(cur, content_id, form["content_type"], form)

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
        await _upsert_subtype(cur, content_id, content_type, form)

    conn.commit()

    load_content_embeddings(conn, get_model(), content_id=content_id)

    return RedirectResponse("/content", status_code=303)


@router.post("/{content_id}/delete")
def delete_content(content_id: str, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM CONTENT WHERE id = %s", (content_id,))
    conn.commit()
    return RedirectResponse("/content", status_code=303)
