import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId


def load_env_file(env_path):
    if not os.path.exists(env_path):
        return

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
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
        return

    load_dotenv(env_path)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_env_file(os.path.join(BASE_DIR, ".env"))

from graph.simple_graph import run_chat
from graph.exam_analysis import analyze_exam_attempt
from graph.exam_generator import generate_exam

app = FastAPI()

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in FastAPI/.env")
print(f"Using MongoDB URI: {MONGODB_URI}")

client = MongoClient(MONGODB_URI)
db = client.get_default_database()
MAIN_COLLECTION = "main_book"
MAIN_DOC_ID = "main_book"
QUESTION_COUNT_MIN = 1
QUESTION_COUNT_MAX = 50


class ChatRequest(BaseModel):
    message: str
    user_id: str
    chapter_name: str
    lesson_name: str


class ChatResponse(BaseModel):
    response: str


class HistoryResponse(BaseModel):
    history: list


class ExamSelection(BaseModel):
    chapterName: str
    topicNames: list[str]


class ExamGenerateRequest(BaseModel):
    selections: list[ExamSelection]
    questionCount: int


class ExamQuestion(BaseModel):
    id: str
    chapterName: str
    topicName: str
    question: str
    options: list[str]
    correctOptionIndex: int


class ExamGenerateResponse(BaseModel):
    questions: list[ExamQuestion]


class WrongExamQuestion(BaseModel):
    id: str
    chapterName: str
    topicName: str
    question: str
    options: list[str]
    correctOptionIndex: int
    selectedOptionIndex: int


class ExamRecommendedTopic(BaseModel):
    chapterName: str
    topicName: str
    reason: str


class ExamSummary(BaseModel):
    headline: str
    overallComment: str
    weaknesses: list[str]
    recommendedTopics: list[ExamRecommendedTopic]
    studyAdvice: list[str]


class ExamAnalyzeRequest(BaseModel):
    selections: list[ExamSelection]
    questionCount: int
    questions: list[ExamQuestion]
    answers: dict[str, int]
    score: int
    percentage: int
    scoreComment: str
    wrongQuestions: list[WrongExamQuestion]


class ExamAnalyzeResponse(BaseModel):
    summary: ExamSummary


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


@app.post("/exam/generate", response_model=ExamGenerateResponse)
async def generate_exam_route(payload: ExamGenerateRequest):
    if payload.questionCount < QUESTION_COUNT_MIN or payload.questionCount > QUESTION_COUNT_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"questionCount must be an integer between {QUESTION_COUNT_MIN} and {QUESTION_COUNT_MAX}",
        )

    selections = sanitize_exam_selections(payload.selections)
    if not selections:
        raise HTTPException(status_code=400, detail="At least one selected topic is required")

    selected_lessons = load_selected_lessons(selections)
    if not selected_lessons:
        raise HTTPException(status_code=404, detail="Selected lessons were not found")

    try:
        questions = generate_exam(selected_lessons, payload.questionCount)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ExamGenerateResponse(questions=[ExamQuestion(**question) for question in questions])


@app.post("/exam/analyze", response_model=ExamAnalyzeResponse)
async def analyze_exam_route(payload: ExamAnalyzeRequest):
    if payload.questionCount < QUESTION_COUNT_MIN or payload.questionCount > QUESTION_COUNT_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"questionCount must be an integer between {QUESTION_COUNT_MIN} and {QUESTION_COUNT_MAX}",
        )

    selections = sanitize_exam_selections(payload.selections)
    if not selections:
        raise HTTPException(status_code=400, detail="At least one selected topic is required")

    if not payload.questions:
        raise HTTPException(status_code=400, detail="Completed exam questions are required")

    if len(payload.answers) != len(payload.questions):
        raise HTTPException(status_code=400, detail="All questions must be answered before analysis")

    try:
        summary = analyze_exam_attempt(payload.model_dump(), ExamSummary)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ExamAnalyzeResponse(summary=ExamSummary(**summary))


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


def sanitize_exam_selections(raw_selections):
    merged = {}

    for selection in raw_selections or []:
        chapter_name = str(getattr(selection, "chapterName", "") or "").strip()
        if not chapter_name:
            continue

        chapter_key = normalize_title(chapter_name)
        if chapter_key not in merged:
            merged[chapter_key] = {
                "chapterName": chapter_name,
                "topicNames": [],
            }

        seen_topics = {normalize_title(name) for name in merged[chapter_key]["topicNames"]}
        for raw_topic_name in getattr(selection, "topicNames", []) or []:
            topic_name = str(raw_topic_name or "").strip()
            topic_key = normalize_title(topic_name)
            if not topic_name or topic_key in seen_topics:
                continue
            merged[chapter_key]["topicNames"].append(topic_name)
            seen_topics.add(topic_key)

    return [item for item in merged.values() if item["topicNames"]]


def get_lesson_label(lesson, fallback):
    return (
        lesson.get("lesson_name")
        or lesson.get("lesson_name_bn")
        or lesson.get("lesson_title")
        or fallback
    )


def load_selected_lessons(selections):
    items = get_main_items()
    selected_lessons = []
    missing_entries = []

    for selection in selections:
        chapter_name = selection["chapterName"]
        match = find_chapter_item(items, chapter_name)
        if not match:
            missing_entries.append(f"Chapter not found: {chapter_name}")
            continue

        source = get_chapter_source(match)
        for topic_name in selection["topicNames"]:
            lesson = find_lesson(source, topic_name)
            if not lesson:
                missing_entries.append(f"Topic not found: {chapter_name} / {topic_name}")
                continue

            content = str(lesson.get("content") or "").strip()
            if not content:
                missing_entries.append(f"Topic content not found: {chapter_name} / {topic_name}")
                continue

            selected_lessons.append(
                {
                    "chapter_name": chapter_name,
                    "topic_name": get_lesson_label(lesson, topic_name),
                    "content": content,
                }
            )

    if missing_entries:
        raise HTTPException(status_code=404, detail="; ".join(missing_entries))

    return selected_lessons


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
