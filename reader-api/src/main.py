from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from src.ingest.router import router as ingest_router
from src.public.router import router as public_router
from src.schemas import HealthzResponse

app = FastAPI(title="NovelTL Reader API", version="0.1.0")


@app.middleware("http")
async def ingest_no_store_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    if request.url.path == "/ingest" or request.url.path.startswith("/ingest/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz", response_model=HealthzResponse, operation_id="healthz")
async def healthz() -> HealthzResponse:
    return HealthzResponse(ok=True)


app.include_router(ingest_router)
app.include_router(public_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
