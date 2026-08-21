from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.db import get_connection
from app.search import search_content

router = APIRouter(prefix="/search")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def search(request: Request, q: str = "", conn=Depends(get_connection)):
    results = search_content(conn, q) if q.strip() else []
    return templates.TemplateResponse(
        request, "search/results.html", {"query": q, "results": results}
    )
