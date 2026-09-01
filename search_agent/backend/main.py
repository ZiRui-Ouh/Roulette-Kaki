from fastapi import FastAPI

from agents.search import answer_question

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Search Agent backend is running!"}


@app.post("/search")
def search(q: str, urls: list[str] | None = None):
    answer = answer_question(question=q, urls=urls or [])
    return {"answer": answer}
