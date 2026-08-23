import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.db import pool
from app.routers import category, content, search, tag, user
from app.routers.content import get_model
from embeddings.load_content_embeddings import load_content_embeddings

logger = logging.getLogger(__name__)


def _run_initial_embeddings():
    try:
        logger.info("Generando embeddings iniciales...")
        with pool.connection() as conn:
            load_content_embeddings(conn, get_model())
        logger.info("Embeddings iniciales completados.")
    except Exception as exc:
        logger.warning("No se pudieron generar embeddings iniciales: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_run_initial_embeddings, daemon=True).start()
    yield


app = FastAPI(title="TP Integrador BDIA", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")

app.include_router(category.router)
app.include_router(tag.router)
app.include_router(user.router)
app.include_router(content.router)
app.include_router(search.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {})
