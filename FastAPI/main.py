import os

from typing import Optional

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="openai/gpt-oss-120b", api_key=GROQ_API_KEY) if GROQ_API_KEY else None


class ChatRequest(BaseModel):
    message: str
    system: Optional[str] = None


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    if llm is None:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set")

    messages = []
    if payload.system:
        messages.append(SystemMessage(content=payload.system))
    messages.append(HumanMessage(content=payload.message))

    result = await llm.ainvoke(messages)
    return ChatResponse(response=result.content)
