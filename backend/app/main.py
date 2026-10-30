import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import analysis, auth, dashboard, documents, health
from .core.config import get_settings
from .core.db import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Forensic AI Lab API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": resp.headers.get("Cache-Control", "no-store")})
        return resp

    @app.exception_handler(HTTPException)
    async def http_exc(_: Request, exc: HTTPException):
        return JSONResponse({"error": {"code": exc.status_code, "message": exc.detail}}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def val_exc(_: Request, exc: RequestValidationError):
        msgs = [f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg'].removeprefix('Value error, ')}" for e in exc.errors()]
        return JSONResponse({"error": {"code": 422, "message": "; ".join(msgs) or "Invalid request."}}, status_code=422)

    @app.exception_handler(Exception)
    async def any_exc(_: Request, exc: Exception):
        logging.getLogger("forensic").exception("Unhandled error")
        return JSONResponse({"error": {"code": 500, "message": "Internal server error."}}, status_code=500)

    for r in (health.router, auth.router, documents.router, analysis.router, dashboard.router):
        app.include_router(r)
    return app


app = create_app()
