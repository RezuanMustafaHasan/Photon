import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId

from graph.simple_graph import run_chat


def load_env_file(env_path):
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.dirname(__file__)
load_env_file(os.path.join(BASE_DIR, ".env"))

app = FastAPI()

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in FastAPI/.env")
print(f"Using MongoDB URI: {MONGODB_URI}")

client = MongoClient(MONGODB_URI)
db = client.get_default_database()
MAIN_COLLECTION = "main_book"
MAIN_DOC_ID = "main_book"


class ChatRequest(BaseModel):
    message: str
    user_id: str
    chapter_name: str
    lesson_name: str


class ChatResponse(BaseModel):
    response: str


class HistoryResponse(BaseModel):
    history: list


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    log_path = os.path.join(os.path.dirname(__file__), "incoming_requests.txt")
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"Incoming request: {payload.json()}\n")
    if not payload.message or not payload.user_id or not payload.chapter_name or not payload.lesson_name:
        raise HTTPException(status_code=400, detail="message, user_id, chapter_name, lesson_name are required")

    lesson = load_lesson(payload.chapter_name, payload.lesson_name)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    history = load_chat_history(payload.user_id, payload.chapter_name, payload.lesson_name)
    lesson_text = json.dumps(lesson, ensure_ascii=False)
    thread_id = f"{payload.user_id}:{payload.chapter_name}:{payload.lesson_name}"
    try:
        response_text = run_chat(thread_id, lesson_text, history, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": response_text})
    save_chat_history(payload.user_id, payload.chapter_name, payload.lesson_name, history)
    return ChatResponse(response=response_text)


@app.get("/history", response_model=HistoryResponse)
async def history(user_id: str, chapter_name: str, lesson_name: str):
    if not user_id or not chapter_name or not lesson_name:
        raise HTTPException(status_code=400, detail="user_id, chapter_name, lesson_name are required")
    history_data = load_chat_history(user_id, chapter_name, lesson_name)
    return HistoryResponse(history=history_data)


def normalize_title(value):
    return str(value or "").strip().lower()


def get_main_items():
    doc = db[MAIN_COLLECTION].find_one({"_id": MAIN_DOC_ID}) or {}
    items = doc.get("items") or []
    return items if isinstance(items, list) else []


def get_chapter_source(item):
    if isinstance(item, dict) and isinstance(item.get("content"), dict):
        return item.get("content")
    return item


def find_chapter_item(items, title):
    target = normalize_title(title)
    for item in items:
        source = get_chapter_source(item)
        names = [
            source.get("chapter_name"),
            source.get("chapter_name_bn"),
            item.get("name") if isinstance(item, dict) else None,
        ]
        if any(normalize_title(name) == target for name in names):
            return item
    return None


def find_lesson(source, lesson_name):
    target = normalize_title(lesson_name)
    lessons = source.get("lessons") if isinstance(source, dict) else None
    if isinstance(lessons, list):
        for entry in lessons:
            name = entry.get("lesson_name") or entry.get("lesson_name_bn") or entry.get("lesson_title")
            number = entry.get("lesson-no") or entry.get("lesson_no")
            if normalize_title(name) == target or normalize_title(number) == target:
                return entry
    boundaries = source.get("lesson_boundaries") if isinstance(source, dict) else None
    if isinstance(boundaries, list):
        for title in boundaries:
            if normalize_title(title) == target:
                return {"lesson_name": title}
    return None


def load_lesson(chapter_name, lesson_name):
    items = get_main_items()
    match = find_chapter_item(items, chapter_name)
    if not match:
        return None
    source = get_chapter_source(match)
    return find_lesson(source, lesson_name)


def parse_user_id(user_id):
    try:
        return ObjectId(user_id)
    except Exception:
        return user_id


def load_chat_history(user_id, chapter_name, lesson_name):
    key = parse_user_id(user_id)
    doc = db["chats"].find_one(
        {"user_id": key, "chapter_name": chapter_name, "lesson_name": lesson_name}
    ) or {}
    history = doc.get("history") or []
    return history if isinstance(history, list) else []


def save_chat_history(user_id, chapter_name, lesson_name, history):
    key = parse_user_id(user_id)
    db["chats"].update_one(
        {"user_id": key, "chapter_name": chapter_name, "lesson_name": lesson_name},
        {"$set": {"history": history}},
        upsert=True,
    )
