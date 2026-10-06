from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
