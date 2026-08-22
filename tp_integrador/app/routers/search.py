from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.db import get_connection
from app.preferences import get_user_max_results
from app.search import search_content

router = APIRouter(prefix="/search")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def search(request: Request, q: str = "", user_id: str = "", conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute('SELECT id, username FROM "user" ORDER BY username')
        users = cur.fetchall()

    max_results = get_user_max_results(conn, user_id, default=10) if user_id else 10
    results = (
        search_content(conn, q, user_id=user_id, limit=max_results)
        if q.strip()
        else []
    )
    return templates.TemplateResponse(
        request,
        "search/results.html",
        {
            "query": q,
            "results": results,
            "users": users,
            "selected_user_id": user_id,
            "max_results": max_results,
        },
    )
