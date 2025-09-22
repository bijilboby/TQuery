# api_server.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llm_chain import ask_question

app = FastAPI()

# Allow your Streamlit frontend to access this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or set to ["http://localhost:8501"] for tighter security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class QuestionRequest(BaseModel):
    query: str

# Response model
class AnswerResponse(BaseModel):
    answer: str

@app.post("/ask", response_model=AnswerResponse)
async def ask_api(request: QuestionRequest):
    query = request.query
    print(f"\n🔍 API REQUEST: {query}")
    response = ask_question(query)
    print(f"✅ API RESPONSE: {response}")
    return {"answer": response}
