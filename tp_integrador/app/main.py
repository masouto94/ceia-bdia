from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.routers import category, content, search, tag, user

app = FastAPI(title="TP Integrador BDIA")
templates = Jinja2Templates(directory="app/templates")

app.include_router(category.router)
app.include_router(tag.router)
app.include_router(user.router)
app.include_router(content.router)
app.include_router(search.router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {})
