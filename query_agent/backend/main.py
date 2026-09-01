from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.query import answer_question

app = FastAPI(
    title="Policy Query Agent Backend",
    description="Backend API for Singapore Policy Query Agent with integrated Search Agent intelligence.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str
    urls: list[str] | None = None


@app.get("/")
def home():
    return {
        "message": "Query Agent backend is running!",
        "search_agent_integrated": True,
    }


@app.post("/query")
def query(q: QueryRequest):
    answer = answer_question(
        question=q.question,
        urls=q.urls,
    )

    return {"answer": answer}