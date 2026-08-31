from fastapi import FastAPI
from agents.query import answer_question

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Query Agent backend is running!"}


@app.post("/query")
def query(q: str):
    answer = answer_question(
        question=q,
        official_sources=[]
    )

    return {"answer": answer}