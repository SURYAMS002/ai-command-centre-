from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database.database import init_db
from app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and seed sample data
    init_db()
    yield
    # Shutdown: clean up if needed

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI-Agent-Based Farm Operations Command Centre (AFOCC)",
    lifespan=lifespan
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
