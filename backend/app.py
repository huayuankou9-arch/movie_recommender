from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_evaluation import router as evaluation_router
from backend.api.routes_home import router as home_router
from backend.api.routes_movies import router as movies_router
from backend.api.routes_recommend import router as recommend_router
from backend.api.routes_users import router as users_router

app = FastAPI(title="Movie Recommender API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(home_router)
app.include_router(recommend_router)
app.include_router(users_router)
app.include_router(movies_router)
app.include_router(evaluation_router)


@app.get("/")
def root():
    return {"message": "Movie Recommender API running", "docs": "/docs"}
