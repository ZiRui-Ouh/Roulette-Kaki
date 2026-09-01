from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.query import answer_question

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "Query Agent backend is running!"}


@app.post("/query")
def query(q: QueryRequest):
    answer = answer_question(
        question=q.question,
        official_sources=[]
    )

    return {"answer": answer}