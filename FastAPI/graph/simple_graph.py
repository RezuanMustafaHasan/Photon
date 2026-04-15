import hashlib
import json
import os
import re
import uuid

from typing import Annotated, Any

try:
    from typing_extensions import TypedDict
except ModuleNotFoundError:
    from typing import TypedDict

try:
    from langchain_core.messages import (
        AIMessage,
        BaseMessage,
        HumanMessage,
        RemoveMessage,
        SystemMessage,
        ToolMessage,
        messages_from_dict,
        messages_to_dict,
    )
    from langchain_core.tools import tool
    from langchain_groq import ChatGroq
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langgraph.prebuilt.tool_node import InjectedState
except (ImportError, ModuleNotFoundError):
    class BaseMessage:
        def __init__(self, content=None, id=None, name=None, **kwargs):
            del kwargs
            self.content = content
            self.id = id
            self.name = name
            self.tool_calls = []

    class AIMessage(BaseMessage):
        pass

    class HumanMessage(BaseMessage):
        pass

    class SystemMessage(BaseMessage):
        pass

    class ToolMessage(BaseMessage):
        pass

    class RemoveMessage(BaseMessage):
        pass

    def messages_from_dict(_items):
        return []

    def messages_to_dict(_items):
        return []

    def tool(_name):
        def decorator(fn):
            return fn

        return decorator

    class ChatGroq:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            raise RuntimeError("ChatGroq is unavailable")

    class MemorySaver:
        def delete_thread(self, *_args, **_kwargs):
            return None

    class _GraphStub:
        def invoke(self, *_args, **_kwargs):
            raise RuntimeError("langgraph is unavailable")

        def get_state(self, *_args, **_kwargs):
            return type("Snapshot", (), {"values": {}})()

    class StateGraph:
        def __init__(self, *_args, **_kwargs):
            pass

        def add_node(self, *_args, **_kwargs):
            pass

        def add_edge(self, *_args, **_kwargs):
            pass

        def add_conditional_edges(self, *_args, **_kwargs):
            pass

        def compile(self, **_kwargs):
            return _GraphStub()

    class ToolNode:
        def __init__(self, *_args, **_kwargs):
            pass

    class InjectedState:
        def __init__(self, field=None):
            self.field = field

    START = object()
    END = object()

    def add_messages(existing, incoming):
        current = list(existing or [])
        current.extend(incoming or [])
        return current

from graph.exam_generator import extract_json_text, normalize_error_message
from graph.lesson_grounding import (
    lesson_source_label,
    normalize_lesson_key,
    retrieve_relevant_lesson_chunks,
    truncate_text,
)
from graph.llm_logging import invoke_llm_with_logging


memory = MemorySaver()
lesson_image_loader = None

IMAGE_TOOL_NAME = "fetch_lesson_image"
DONE_TOKEN = "DONE"
MAX_RECENT_TURNS = 4
MAX_RECENT_MESSAGE_CHARS = 4500
MAX_SUMMARY_BATCH_CHARS = 2600
MAX_HISTORY_ITEMS = 8
MAX_TURNS_PER_TOPIC = 4

GROUNDING_SYSTEM_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "You must respond in valid JSON only, with no markdown fences.\n"
    "Return this exact schema:\n"
    "{\n"
    '  "textbook_answer": "lesson-grounded answer",\n'
    '  "extra_explanation": "optional extra explanation"\n'
    "}\n"
    "Rules:\n"
    "- textbook_answer must use only the provided lesson chunks.\n"
    "- If the question is not directly covered by the lesson chunks, say that clearly in textbook_answer.\n"
    "- extra_explanation is optional, but when used it must be clearly lesson-adjacent intuition, example, or clarification.\n"
    "- Do not secretly mix outside knowledge into textbook_answer.\n"
    "- If the exact answer is not present in the lesson chunks but the question is still physics-related and relevant to the current chapter/topic, answer in extra_explanation using your own physics knowledge.\n"
    "- Keep textbook_answer grounded to the lesson, but let extra_explanation be broader when it helps the student understand.\n"
    "- Write clean, readable paragraphs and markdown lists. Do not include the literal characters \\n in normal prose.\n"
    "- When you write formulas or symbols, always use Markdown math delimiters: inline $...$ and block $$...$$.\n"
    "- Because the response is JSON, escape every backslash inside LaTeX so JSON stays valid.\n"
    "- For multiplied units or symbols, use LaTeX operators like \\cdot and \\times inside math, not Unicode characters like · or ×.\n"
    "- When writing units such as newton-meter, prefer $N \\cdot m$ instead of text like N·m inside math.\n"
    "- Do not write raw LaTeX commands like \\frac outside math delimiters.\n"
    "- Keep Bangla words outside the math delimiters whenever possible.\n"
    "- When listing formulas, prefer short markdown bullets and wrap each formula in $...$ or $$...$$.\n"
    "- Keep the tone simple, student-friendly, and concise.\n"
    "- Prefer Bangla if the lesson or student message is primarily Bangla; otherwise match the student's language."
)
INVALID_JSON_BACKSLASH_PATTERN = re.compile(r'(?<!\\)\\(?!["\\/bfnrtu])')
LATEX_COMMAND_BACKSLASH_PATTERN = re.compile(
    r"(?<!\\)\\(?=(?:frac|int|sum|sqrt|cdot|times|left|right|vec|hat|theta|phi|pi|alpha|beta|gamma|lambda|mu|nu|rho|sigma|omega|Delta|delta|tau|sin|cos|tan|text|mathrm|mathbf|pm|quad|qquad|leq|geq|neq|approx)\b)"
)
LITERAL_NEWLINE_PATTERN = re.compile(r"\\n(?![A-Za-z])")
LITERAL_TAB_PATTERN = re.compile(r"\\t(?![A-Za-z])")

FIGURE_TITLE_PATTERN = re.compile(r"চিত্র\s*[0-9০-৯]+(?:\.[0-9০-৯]+)*\s*:\s*([^\n]+)")

UNDERSTOOD_HINTS = {
    "bujhsi",
    "bujhesi",
    "bujhlam",
    "bujhte perechi",
    "understood",
    "got it",
    "okay",
    "ok",
    "yes",
    "yeah",
    "right",
    "correct",
    "ji",
    "sure",
    "clear",
    "continue",
    "next",
    "move on",
    "পরের",
    "পরেরটা",
    "আগাও",
    "এগাও",
    "চলো",
    "হ্যাঁ",
    "হ্যা",
    "জি",
    "ঠিক",
    "বুঝছি",
    "বুঝেছি",
    "বুঝলাম",
    "ক্লিয়ার",
    "পরবর্তী",
}

CONFUSION_HINTS = {
    "don't understand",
    "dont understand",
    "confused",
    "again",
    "repeat",
    "why",
    "how",
    "what",
    "বুঝিনি",
    "বুঝি নাই",
    "আবার",
    "কেন",
    "কী",
    "কি",
    "কিভাবে",
    "ব্যাখ্যা",
    "explain",
    "explanation",
}

CONTINUE_HINTS = {
    "continue",
    "next",
    "move on",
    "go on",
    "carry on",
    "পরের",
    "পরেরটা",
    "পরবর্তী",
    "এগাও",
    "আগাও",
    "চলো",
}


class LessonSummary(TypedDict, total=False):
    taught_concepts: list[str]
    understood: list[str]
    confusion: list[str]
    next_to_teach: str


class ThreadStateSnapshot(TypedDict, total=False):
    chapter_name: str
    lesson_name: str
    lesson_signature: str
    chat_model: str
    current_topic_index: int
    current_topic_turns: int
    topic_complete: bool
    lesson_summary: LessonSummary
    awaiting_reply: bool
    lesson_complete: bool
    used_image_ids: list[str]
    checkpoint_indexes: list[int]
    recent_messages: list[dict[str, Any]]


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    chapter_name: str
    lesson_name: str
    chat_model: str
    topics: list[dict[str, str]]
    current_topic_index: int
    current_topic_turns: int
    current_topic: dict[str, str]
    topic_complete: bool
    pending_action: str
    checkpoint_indexes: list[int]
    used_image_ids: list[str]
    lesson_summary: LessonSummary
    awaiting_reply: bool
    lesson_complete: bool


DEFAULT_CHAT_MODEL = "groq:openai/gpt-oss-120b"
DEFAULT_CHAT_MODEL_CONFIG = {
    "id": DEFAULT_CHAT_MODEL,
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
}


def configure_image_loader(loader):
    global lesson_image_loader
    lesson_image_loader = loader


def repair_invalid_json_backslashes(value):
    text = str(value or "")
    text = LATEX_COMMAND_BACKSLASH_PATTERN.sub(r"\\\\", text)
    return INVALID_JSON_BACKSLASH_PATTERN.sub(r"\\\\", text)


def normalize_grounded_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = LITERAL_NEWLINE_PATTERN.sub("\n", text)
    text = LITERAL_TAB_PATTERN.sub(" ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_chat_model_config(selected_model=None):
    requested = str(selected_model or "").strip()
    if not requested:
        return dict(DEFAULT_CHAT_MODEL_CONFIG)

    provider = ""
    model = ""
    if ":" in requested:
        provider, model = requested.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()

    if provider in {"openai", "groq"} and model:
        return {
            "id": f"{provider}:{model}",
            "provider": provider,
            "model": model,
        }

    return dict(DEFAULT_CHAT_MODEL_CONFIG)


def resolve_chat_model_id(selected_model=None):
    return parse_chat_model_config(selected_model)["id"]


def resolve_chat_model_config(selected_model=None):
    return parse_chat_model_config(selected_model)


def get_state_chat_model(state):
    return resolve_chat_model_id((state or {}).get("chat_model"))


def get_missing_chat_model_key_message(selected_model=None):
    provider = resolve_chat_model_config(selected_model)["provider"]
    if provider == "openai":
        return "OPENAI_API_KEY is not set"
    return "GROQ_API_KEY is not set"


def get_llm(selected_model=None):
    model_config = resolve_chat_model_config(selected_model)

    if model_config["provider"] == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            from langchain_openai import ChatOpenAI
        except (ImportError, ModuleNotFoundError) as exc:
            raise ValueError("langchain-openai is not installed") from exc

        return ChatOpenAI(model=model_config["model"], api_key=api_key, temperature=0)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(model=model_config["model"], api_key=api_key, temperature=0)


def extract_text_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(part for part in parts if part).strip()

    return str(content or "").strip()


def normalize_text(value):
    return str(value or "").strip().lower()


def tokenize(value):
    return set(re.findall(r"[a-z0-9\u0980-\u09ff]+", normalize_text(value)))


def parse_json_from_text(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        try:
            return json.loads(text[object_start:object_end + 1])
        except Exception:
            return None

    return None


def compose_chat_markdown(textbook_answer, extra_explanation, citations):
    textbook_answer = normalize_grounded_text(textbook_answer)
    extra_explanation = normalize_grounded_text(extra_explanation)
    parts = []

    if textbook_answer:
        parts.append(f"**From your lesson**\n\n{textbook_answer}")

    if extra_explanation:
        parts.append(f"**Extra explanation**\n\n{extra_explanation}")

    if citations:
        citation_lines = [
            f"- {citation['section_label']}"
            for citation in citations
            if citation.get("section_label")
        ]
        if citation_lines:
            parts.append("**Sources**\n" + "\n".join(citation_lines))

    return "\n\n".join(part for part in parts if part).strip()


def assistant_history_text(item):
    content = str(item.get("content") or "").strip()
    if content:
        return content

    textbook_answer = str(item.get("textbook_answer") or "").strip()
    extra_explanation = str(item.get("extra_explanation") or "").strip()
    citations = item.get("citations") if isinstance(item.get("citations"), list) else []
    return compose_chat_markdown(textbook_answer, extra_explanation, citations)


def normalize_topics(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    return []


def build_image_id(item, fallback_index):
    raw_parts = [
        str(item.get("imageURL") or item.get("imageUrl") or item.get("url") or item.get("secure_url") or ""),
        str(item.get("description") or item.get("caption") or ""),
        json.dumps(normalize_topics(item.get("topic") if "topic" in item else item.get("topics")), ensure_ascii=False),
        str(fallback_index),
    ]
    digest = hashlib.sha1("|".join(raw_parts).encode("utf-8")).hexdigest()
    return f"img_{digest[:12]}"


def normalize_image_record(item, fallback_index=0):
    if not isinstance(item, dict):
        return None

    image_url = (
        item.get("imageURL")
        or item.get("imageUrl")
        or item.get("url")
        or item.get("secure_url")
    )
    image_url = str(image_url or "").strip()
    if not image_url:
        return None

    description = str(item.get("description") or item.get("caption") or "").strip()
    topics = normalize_topics(item.get("topic") if "topic" in item else item.get("topics"))

    return {
        "image_id": build_image_id(item, fallback_index),
        "imageURL": image_url,
        "description": description,
        "topic": topics,
    }


def compact_image_metadata(image):
    return {
        "image_id": str(image.get("image_id") or "").strip(),
        "imageURL": str(image.get("imageURL") or "").strip(),
        "description": str(image.get("description") or "").strip(),
    }


def normalize_images_for_response(raw_images):
    if not isinstance(raw_images, list):
        return []

    normalized = []
    for index, item in enumerate(raw_images):
        image = normalize_image_record(item, fallback_index=index)
        if image:
            normalized.append(
                {
                    "image_id": image["image_id"],
                    "imageURL": image["imageURL"],
                    "description": image["description"],
                    "topic": image["topic"],
                }
            )

    return normalized


def normalize_topic_entry(raw_topic, index=0, lesson_name=""):
    if isinstance(raw_topic, dict):
        title = str(raw_topic.get("title") or raw_topic.get("topic_title") or raw_topic.get("name") or "").strip()
        content = str(raw_topic.get("content") or raw_topic.get("text") or "").strip()
    else:
        title = ""
        content = str(raw_topic or "").strip()

    if not title:
        if lesson_name and index == 0:
            title = lesson_name
        else:
            title = f"Topic {index + 1}"

    return {
        "title": title,
        "content": content,
    }


def normalize_lesson_topics(lesson_source, fallback_lesson_name=""):
    if isinstance(lesson_source, str):
        parsed = parse_json_from_text(lesson_source)
        if isinstance(parsed, dict):
            return normalize_lesson_topics(parsed, fallback_lesson_name=fallback_lesson_name)
        content = lesson_source.strip()
        if content:
            return [normalize_topic_entry({"title": fallback_lesson_name or "Lesson", "content": content}, 0, fallback_lesson_name)]
        return []

    if not isinstance(lesson_source, dict):
        return []

    lesson_name = (
        str(lesson_source.get("lesson_name") or lesson_source.get("lesson_name_bn") or lesson_source.get("lesson_title") or fallback_lesson_name)
        .strip()
    )
    raw_topics = lesson_source.get("topics")
    if isinstance(raw_topics, list):
        normalized = [
            normalize_topic_entry(topic, index=index, lesson_name=lesson_name)
            for index, topic in enumerate(raw_topics)
        ]
        return [topic for topic in normalized if topic.get("content")]

    content = str(lesson_source.get("content") or lesson_source.get("lesson_text") or lesson_source.get("text") or "").strip()
    if not content:
        return []

    return [normalize_topic_entry({"title": lesson_name or "Lesson", "content": content}, 0, lesson_name)]


def flatten_lesson_topics_to_text(lesson_source):
    topics = normalize_lesson_topics(lesson_source)
    parts = []
    for topic in topics:
        title = str(topic.get("title") or "").strip()
        content = str(topic.get("content") or "").strip()
        if title:
            parts.append(title)
        if content:
            parts.append(content)
    return "\n\n".join(parts).strip()


def compute_lesson_signature(topics):
    payload = [
        {
            "title": str(topic.get("title") or "").strip(),
            "content": str(topic.get("content") or "").strip(),
        }
        for topic in topics or []
        if isinstance(topic, dict)
    ]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_topic_preview(topic, limit=140):
    normalized = normalize_topic_entry(topic)
    title = str(normalized.get("title") or "").strip()
    if title:
        preview = re.sub(r"\s+", " ", title).strip()
    else:
        preview = re.sub(r"\s+", " ", str(normalized.get("content") or "").strip())

    if len(preview) <= limit:
        return preview
    return preview[: limit - 3].rstrip() + "..."


def first_sentence(text, limit=220):
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[।.!?])\s+", cleaned)
    sentence = parts[0].strip() if parts else cleaned
    if len(sentence) <= limit:
        return sentence
    return sentence[: limit - 3].rstrip() + "..."


def extract_figure_hints(topic_content):
    hints = []
    seen = set()
    for match in FIGURE_TITLE_PATTERN.findall(str(topic_content or "")):
        hint = str(match or "").strip()
        key = normalize_text(hint)
        if not hint or key in seen:
            continue
        seen.add(key)
        hints.append(hint)
    return hints


def default_lesson_summary():
    return {
        "taught_concepts": [],
        "understood": [],
        "confusion": [],
        "next_to_teach": "",
    }


def ensure_message_ids(messages, prefix="msg"):
    ensured = []
    for message in messages or []:
        if not getattr(message, "id", None):
            message.id = f"{prefix}-{uuid.uuid4()}"
        ensured.append(message)
    return ensured


def dedupe_short_strings(values, max_items=6, max_chars=120):
    seen = set()
    cleaned = []

    for value in values or []:
        item = re.sub(r"\s+", " ", str(value or "").strip())
        if not item:
            continue
        item = item[:max_chars].strip()
        key = normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break

    return cleaned


def sanitize_summary(summary, fallback_next=""):
    source = summary if isinstance(summary, dict) else {}
    return {
        "taught_concepts": dedupe_short_strings(source.get("taught_concepts"), max_items=8),
        "understood": dedupe_short_strings(source.get("understood"), max_items=6),
        "confusion": dedupe_short_strings(source.get("confusion"), max_items=6),
        "next_to_teach": str(source.get("next_to_teach") or fallback_next or "").strip()[:180],
    }


def merge_summaries(existing_summary, incoming_summary, fallback_next=""):
    existing = sanitize_summary(existing_summary, fallback_next=fallback_next)
    incoming = sanitize_summary(
        incoming_summary,
        fallback_next=incoming_summary.get("next_to_teach") if isinstance(incoming_summary, dict) else fallback_next,
    )
    return {
        "taught_concepts": dedupe_short_strings(existing["taught_concepts"] + incoming["taught_concepts"], max_items=8),
        "understood": dedupe_short_strings(existing["understood"] + incoming["understood"], max_items=6),
        "confusion": dedupe_short_strings(existing["confusion"] + incoming["confusion"], max_items=6),
        "next_to_teach": str(incoming.get("next_to_teach") or existing.get("next_to_teach") or fallback_next or "").strip()[:180],
    }


def merge_note(existing_items, new_item, max_items=6):
    values = list(existing_items or [])
    if new_item:
        values.append(new_item)
    return dedupe_short_strings(values, max_items=max_items)


def build_next_teaching_note(current_topic_preview, next_topic_preview, waiting_for_student):
    if not current_topic_preview and not next_topic_preview:
        return ""
    if waiting_for_student and current_topic_preview and next_topic_preview:
        return f"{current_topic_preview} বুঝেছে কি না নিশ্চিত করে তারপর {next_topic_preview}"
    if waiting_for_student and current_topic_preview:
        return f"{current_topic_preview} বুঝেছে কি না নিশ্চিত করা"
    return next_topic_preview or current_topic_preview


def build_next_progress_note(current_topic_preview, next_topic_preview, waiting_for_student, topic_complete):
    if not topic_complete:
        if waiting_for_student and current_topic_preview:
            return f"{current_topic_preview} এর পরের ছোট অংশ শেখানো"
        return current_topic_preview or next_topic_preview
    return build_next_teaching_note(current_topic_preview, next_topic_preview, waiting_for_student)


def format_summary_for_prompt(summary):
    data = sanitize_summary(summary)
    sections = [
        f"Taught already: {', '.join(data['taught_concepts']) or 'nothing yet'}",
        f"Student understood: {', '.join(data['understood']) or 'not clear yet'}",
        f"Student confusion: {', '.join(data['confusion']) or 'none noted'}",
        f"What should happen next: {data['next_to_teach'] or 'teach the current topic simply'}",
    ]
    return "\n".join(sections)


def build_history_messages(history):
    messages = []
    for item in history or []:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = assistant_history_text(item) if role == "assistant" else extract_text_content(item.get("content"))
        if not content:
            continue

        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    return ensure_message_ids(messages, prefix="hist")


def build_grounded_history_messages(history):
    messages = []
    recent_history = history[-MAX_HISTORY_ITEMS:] if isinstance(history, list) else []
    for item in recent_history:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = assistant_history_text(item) if role == "assistant" else str(item.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    return messages


def build_retrieval_query(user_text, history):
    context_parts = [str(user_text or "").strip()]
    recent_history = history[-4:] if isinstance(history, list) else []
    for item in reversed(recent_history):
        if not isinstance(item, dict):
            continue
        content = assistant_history_text(item) if item.get("role") == "assistant" else str(item.get("content") or "").strip()
        if not content:
            continue
        context_parts.append(truncate_text(content, max_length=240))
        if len(context_parts) >= 3:
            break
    return "\n".join(reversed([part for part in context_parts if part]))


def build_grounded_prompt(chapter_name, lesson_name, user_text, retrieval):
    retrieval_mode = retrieval.get("mode", "no_match")
    chunks = retrieval.get("chunks") or []
    source_lesson_name = retrieval.get("source_lesson_name") or lesson_name

    if chunks:
        formatted_chunks = []
        for index, chunk in enumerate(chunks, start=1):
            formatted_chunks.append(
                (
                    f"[Chunk {index}]\n"
                    f"Lesson: {chunk.get('lesson_name')}\n"
                    f"Section: {chunk.get('section_label')}\n"
                    f"Text:\n{chunk.get('chunk_text')}"
                )
            )
        context_block = "\n\n".join(formatted_chunks)
    else:
        context_block = "No directly relevant lesson chunk matched the question."

    return (
        f"Current lesson:\n"
        f"- Chapter: {chapter_name}\n"
        f"- Lesson: {lesson_name}\n"
        f"- Best matching lesson: {source_lesson_name}\n"
        f"- Retrieval mode: {retrieval_mode}\n\n"
        "Use the retrieved lesson chunks below for the grounded answer.\n"
        "If the best matching lesson is not the current lesson, treat it as a nearby source lesson from the same chapter.\n"
        "If the lesson does not directly cover the student's question, say that in textbook_answer and keep any broader help in extra_explanation.\n\n"
        f"Retrieved lesson chunks:\n{context_block}\n\n"
        f"Student question:\n{user_text}"
    )


def parse_grounded_response(raw_content):
    raw_output = extract_text_content(raw_content)
    json_text = repair_invalid_json_backslashes(extract_json_text(raw_output))

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The grounded chat JSON is malformed: {exc.msg}.") from exc

    if not isinstance(payload, dict):
        raise ValueError("The grounded chat payload must be a JSON object.")

    textbook_answer = normalize_grounded_text(payload.get("textbook_answer") or "")
    extra_explanation = normalize_grounded_text(payload.get("extra_explanation") or "")

    if not textbook_answer:
        raise ValueError("The grounded chat payload must contain a textbook_answer.")

    return {
        "textbook_answer": textbook_answer,
        "extra_explanation": extra_explanation,
    }


def build_citations(chapter_name, lesson_name, retrieval):
    if retrieval.get("mode") not in {"matched", "intro"}:
        return []

    source_lesson_name = str(retrieval.get("source_lesson_name") or "").strip()
    source_chapter_name = str(retrieval.get("source_chapter_name") or chapter_name).strip()
    if not source_lesson_name:
        return []

    if normalize_lesson_key(source_lesson_name) == normalize_lesson_key(lesson_name):
        return []

    return [
        {
            "chapter_name": source_chapter_name or chapter_name,
            "lesson_name": source_lesson_name,
            "section_label": lesson_source_label(source_chapter_name or chapter_name, source_lesson_name),
            "snippet": "",
        }
    ]


def build_message_transcript(messages, include_tools=True, max_chars=0):
    lines = []
    total = 0

    for message in messages or []:
        if isinstance(message, HumanMessage):
            line = f"Student: {extract_text_content(message.content)}"
        elif isinstance(message, AIMessage):
            line = f"Tutor: {extract_text_content(message.content)}"
        elif include_tools and isinstance(message, ToolMessage):
            line = f"Tool({message.name or 'tool'}): {extract_text_content(message.content)}"
        else:
            continue

        if not line.strip():
            continue

        if max_chars and total + len(line) > max_chars and lines:
            break

        lines.append(line)
        total += len(line)

    return "\n".join(lines).strip()


def group_messages_by_turn(messages):
    groups = []
    current = []

    for message in messages or []:
        if isinstance(message, HumanMessage):
            if current:
                groups.append(current)
            current = [message]
            continue

        if current:
            current.append(message)
        elif groups:
            groups[-1].append(message)
        else:
            current = [message]

    if current:
        groups.append(current)

    return groups


def estimate_group_chars(messages):
    return sum(len(extract_text_content(message.content)) + 24 for message in messages or [])


def trim_message_history(messages, max_turns=MAX_RECENT_TURNS, max_chars=MAX_RECENT_MESSAGE_CHARS):
    if not messages:
        return []

    groups = group_messages_by_turn(messages)
    if not groups:
        return list(messages)[-4:]

    kept_groups = []
    kept_turns = 0
    kept_chars = 0

    for group in reversed(groups):
        group_chars = estimate_group_chars(group)
        group_has_human = any(isinstance(message, HumanMessage) for message in group)

        if kept_groups and group_has_human and kept_turns >= max_turns:
            break
        if kept_groups and kept_chars + group_chars > max_chars:
            break

        kept_groups.insert(0, group)
        kept_chars += group_chars
        if group_has_human:
            kept_turns += 1

    trimmed = [message for group in kept_groups for message in group]
    return trimmed or list(messages)[-4:]


def serialize_messages(messages):
    trimmed = ensure_message_ids(trim_message_history(messages), prefix="snap")
    return messages_to_dict(trimmed)


def deserialize_messages(serialized_messages):
    if not isinstance(serialized_messages, list):
        return []
    try:
        restored = messages_from_dict(serialized_messages)
    except Exception:
        return []
    valid_messages = [message for message in restored if isinstance(message, BaseMessage)]
    return ensure_message_ids(valid_messages, prefix="snap")


def latest_human_message(messages):
    for message in reversed(messages or []):
        if isinstance(message, HumanMessage):
            return message
    return None


def latest_ai_message(messages):
    for message in reversed(messages or []):
        if isinstance(message, AIMessage):
            return message
    return None


def latest_turn_messages(messages):
    groups = group_messages_by_turn(messages)
    return groups[-1] if groups else []


def is_done_response(message):
    if not isinstance(message, AIMessage):
        return False
    return extract_text_content(message.content).strip().upper() == DONE_TOKEN


def contains_any_hint(text, hints):
    normalized = normalize_text(text)
    return any(hint in normalized for hint in hints)


def call_llm_for_json(llm, system_prompt, user_prompt):
    if llm is None:
        return None

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        response = invoke_llm_with_logging(
            llm,
            messages,
            context="simple_graph.call_llm_for_json",
        )
    except Exception:
        return None

    return parse_json_from_text(extract_text_content(response.content))


def fallback_history_summary(messages, current_summary=None):
    summary = sanitize_summary(current_summary)

    for message in messages or []:
        if isinstance(message, AIMessage):
            note = build_topic_preview({"title": "", "content": extract_text_content(message.content)}, limit=100)
            summary["taught_concepts"] = merge_note(summary["taught_concepts"], note, max_items=8)
        elif isinstance(message, HumanMessage):
            text = extract_text_content(message.content)
            short_note = build_topic_preview({"title": "", "content": text}, limit=100)
            if contains_any_hint(text, CONFUSION_HINTS) or "?" in text:
                summary["confusion"] = merge_note(summary["confusion"], short_note)
            elif contains_any_hint(text, UNDERSTOOD_HINTS):
                summary["understood"] = merge_note(summary["understood"], short_note)

    return summary


def split_transcript_batches(transcript, max_chars=MAX_SUMMARY_BATCH_CHARS):
    lines = [line for line in str(transcript or "").splitlines() if line.strip()]
    if not lines:
        return []

    batches = []
    buffer = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1
        if buffer and current_length + line_length > max_chars:
            batches.append("\n".join(buffer))
            buffer = [line]
            current_length = line_length
            continue

        buffer.append(line)
        current_length += line_length

    if buffer:
        batches.append("\n".join(buffer))

    return batches


def summarize_transcript_batch(llm, chapter_name, lesson_name, transcript_batch, current_summary):
    fallback_next = sanitize_summary(current_summary).get("next_to_teach", "")
    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "You summarize a tutoring conversation into compact JSON.\n"
            "Return only valid JSON with these keys:\n"
            "taught_concepts: list[str]\n"
            "understood: list[str]\n"
            "confusion: list[str]\n"
            "next_to_teach: str\n"
            "Rules:\n"
            "- Keep each item short and concrete.\n"
            "- Only use facts from the transcript.\n"
            "- Do not repeat the same point with different wording."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Current summary:\n{json.dumps(sanitize_summary(current_summary), ensure_ascii=False)}\n\n"
            f"Transcript batch:\n{transcript_batch}"
        ),
    )

    if not isinstance(payload, dict):
        return fallback_history_summary([], current_summary)

    return merge_summaries(current_summary, payload, fallback_next=fallback_next)


def summarize_older_conversation(llm, chapter_name, lesson_name, history_messages):
    if not history_messages:
        return default_lesson_summary()

    transcript = build_message_transcript(history_messages, include_tools=False)
    batches = split_transcript_batches(transcript)
    summary = default_lesson_summary()

    if not batches:
        return fallback_history_summary(history_messages, summary)

    for batch in batches:
        updated = summarize_transcript_batch(llm, chapter_name, lesson_name, batch, summary)
        summary = sanitize_summary(updated, fallback_next=summary.get("next_to_teach", ""))

    return fallback_history_summary(history_messages[-6:], summary)


def infer_current_topic_index_heuristic(topics, summary, recent_messages):
    if not topics:
        return 0

    summary_data = sanitize_summary(summary)
    next_hint = summary_data.get("next_to_teach", "")
    recent_text = build_message_transcript(recent_messages, include_tools=False, max_chars=1600)

    if next_hint:
        scores = []
        for index, topic in enumerate(topics):
            topic_text = f"{build_topic_preview(topic)}\n{normalize_topic_entry(topic).get('content', '')}"
            score = len(tokenize(next_hint) & tokenize(topic_text))
            scores.append((score, index))
        scores.sort(reverse=True)
        if scores and scores[0][0] > 0:
            return scores[0][1]

    combined_text = " ".join(
        summary_data.get("taught_concepts", [])
        + summary_data.get("understood", [])
        + summary_data.get("confusion", [])
        + [recent_text]
    )
    if not combined_text.strip():
        return 0

    scores = []
    for index, topic in enumerate(topics):
        topic_text = f"{build_topic_preview(topic)}\n{normalize_topic_entry(topic).get('content', '')}"
        score = len(tokenize(combined_text) & tokenize(topic_text))
        scores.append((score, index))

    scores.sort(reverse=True)
    if scores and scores[0][0] > 0:
        return min(scores[0][1], len(topics) - 1)

    return 0


def infer_current_topic_index(llm, chapter_name, lesson_name, topics, summary, recent_messages):
    if not topics:
        return 0, False

    last_ai = latest_ai_message(recent_messages)
    if is_done_response(last_ai):
        return len(topics), True

    topic_previews = "\n".join(
        f"{index}: {build_topic_preview(topic, limit=120)}"
        for index, topic in enumerate(topics)
    )

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Choose which lesson topic should be active on the next tutoring turn.\n"
            "Return only valid JSON with:\n"
            "current_topic_index: int\n"
            "lesson_complete: bool\n"
            "Rules:\n"
            "- Use 0-based topic indexes.\n"
            "- If the lesson is already fully covered, set lesson_complete true.\n"
            "- Pick the topic that the tutor should work with next."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Running summary:\n{json.dumps(sanitize_summary(summary), ensure_ascii=False)}\n\n"
            f"Recent conversation:\n{build_message_transcript(recent_messages, include_tools=False, max_chars=1800)}\n\n"
            f"Lesson topic previews:\n{topic_previews}"
        ),
    )

    if isinstance(payload, dict):
        try:
            index = int(payload.get("current_topic_index", 0))
        except Exception:
            index = 0
        lesson_complete = bool(payload.get("lesson_complete"))
        index = max(0, min(index, len(topics)))
        if lesson_complete:
            return len(topics), True
        return min(index, len(topics) - 1), False

    return infer_current_topic_index_heuristic(topics, summary, recent_messages), False


def build_initial_thread_summary(llm, chapter_name, lesson_name, topics, history_messages):
    summary = summarize_older_conversation(llm, chapter_name, lesson_name, history_messages)
    recent_messages = trim_message_history(history_messages)
    index, lesson_complete = infer_current_topic_index(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        topics=topics,
        summary=summary,
        recent_messages=recent_messages,
    )
    current_preview = build_topic_preview(topics[index], limit=100) if topics and index < len(topics) else ""
    next_preview = build_topic_preview(topics[index + 1], limit=100) if index + 1 < len(topics) else ""
    summary["next_to_teach"] = (
        ""
        if lesson_complete
        else build_next_progress_note(
            current_preview,
            next_preview,
            waiting_for_student=bool(recent_messages),
            topic_complete=False,
        )
    )
    return sanitize_summary(summary), index, lesson_complete


def checkpoint_interval_for_lesson(total_topics):
    if total_topics <= 2:
        return 1
    if total_topics <= 4:
        return 2
    return 3


def build_checkpoint_indexes(topic_count):
    if topic_count <= 0:
        return []

    interval = checkpoint_interval_for_lesson(topic_count)
    indexes = {topic_count - 1}
    for index in range(topic_count):
        if interval > 0 and (index + 1) % interval == 0:
            indexes.add(index)
    return sorted(indexes)


def normalize_checkpoint_indexes(values, topic_count):
    cleaned = []
    for value in values or []:
        try:
            index = int(value)
        except Exception:
            continue
        if 0 <= index < topic_count and index not in cleaned:
            cleaned.append(index)
    return cleaned or build_checkpoint_indexes(topic_count)


def normalize_used_image_ids(values):
    seen = set()
    cleaned = []
    for value in values or []:
        image_id = str(value or "").strip()
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        cleaned.append(image_id)
    return cleaned


def merge_used_image_ids(existing_ids, images):
    merged = list(normalize_used_image_ids(existing_ids))
    seen = set(merged)
    for image in images or []:
        if not isinstance(image, dict):
            continue
        image_id = str(image.get("image_id") or "").strip()
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        merged.append(image_id)
    return merged


def collect_used_image_ids_from_history(history):
    used_ids = set()

    for entry in history or []:
        if not isinstance(entry, dict) or entry.get("role") != "assistant":
            continue

        for image in entry.get("images") or []:
            if not isinstance(image, dict):
                continue

            image_id = str(image.get("image_id") or "").strip()
            if image_id:
                used_ids.add(image_id)
                continue

            normalized = normalize_image_record(image)
            if normalized:
                used_ids.add(normalized["image_id"])

    return used_ids


def load_images_from_database(chapter_name, lesson_name):
    if lesson_image_loader is None:
        return []

    try:
        raw_images = lesson_image_loader(chapter_name, lesson_name) or []
    except Exception:
        return []

    if not isinstance(raw_images, list):
        return []

    normalized = []
    for index, item in enumerate(raw_images):
        image = normalize_image_record(item, fallback_index=index)
        if image:
            normalized.append(image)

    return normalized


def score_image_relevance(query_text, image):
    query_tokens = tokenize(query_text)
    description_tokens = tokenize(image.get("description"))
    if not query_tokens or not description_tokens:
        return 0

    overlap = len(query_tokens & description_tokens)
    normalized_query = normalize_text(query_text)
    normalized_description = normalize_text(image.get("description"))
    if normalized_query and normalized_query in normalized_description:
        overlap += 2
    return overlap


@tool(IMAGE_TOOL_NAME)
def fetch_lesson_image(
    chapter_name: str,
    lesson_name: str,
    hint: str,
    used_image_ids: Annotated[list[str], InjectedState("used_image_ids")] = None,
) -> str:
    """
    Search lesson images using a চিত্র title hint from the lesson content.
    Reads ALL image descriptions one by one and picks the best unused match.
    Returns compact image metadata or a not-found message.
    """

    images = load_images_from_database(chapter_name, lesson_name)
    excluded_ids = {str(item).strip() for item in used_image_ids or [] if str(item).strip()}

    best_image = None
    best_score = 0
    for image in images:
        image_id = str(image.get("image_id") or "").strip()
        if not image_id or image_id in excluded_ids:
            continue
        score = score_image_relevance(hint, image)
        if score > best_score:
            best_score = score
            best_image = image

    if best_image is None or best_score <= 0:
        return json.dumps({"found": False}, ensure_ascii=False)

    return json.dumps(
        {
            "found": True,
            "image_id": best_image["image_id"],
            "imageURL": best_image["imageURL"],
            "description": best_image["description"],
        },
        ensure_ascii=False,
    )


def extract_selected_images_from_tool_messages(messages):
    selected_images = []
    seen_ids = set()

    for message in messages or []:
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", "") != IMAGE_TOOL_NAME:
            continue

        payload = parse_json_from_text(extract_text_content(message.content))
        if not isinstance(payload, dict) or not payload.get("found"):
            continue

        image_id = str(payload.get("image_id") or "").strip()
        image_url = str(payload.get("imageURL") or "").strip()
        if not image_id or not image_url or image_id in seen_ids:
            continue

        seen_ids.add(image_id)
        selected_images.append(
            {
                "image_id": image_id,
                "imageURL": image_url,
                "description": str(payload.get("description") or "").strip(),
                "topic": [],
            }
        )

    return selected_images


def merge_selected_images(*groups, max_images=8):
    merged = []
    seen_ids = set()

    for group in groups:
        for item in group or []:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id") or "").strip()
            if not image_id or image_id in seen_ids:
                continue
            seen_ids.add(image_id)
            merged.append(
                {
                    "image_id": image_id,
                    "imageURL": str(item.get("imageURL") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "topic": normalize_topics(item.get("topic")),
                }
            )
            if len(merged) >= max_images:
                return merged

    return merged


def resolve_images_for_response(
    chapter_name,
    lesson_name,
    selected_images,
    response_text="",
    current_topic=None,
    chat_model=None,
):
    del response_text, current_topic, chat_model

    if not selected_images:
        return []

    catalog = {
        image["image_id"]: image
        for image in load_images_from_database(chapter_name, lesson_name)
    }
    resolved = []
    for item in selected_images:
        image_id = str(item.get("image_id") or "").strip()
        if not image_id:
            continue

        catalog_item = catalog.get(image_id, {})
        image_url = str(item.get("imageURL") or catalog_item.get("imageURL") or "").strip()
        if not image_url:
            continue

        resolved.append(
            {
                "image_id": image_id,
                "imageURL": image_url,
                "description": str(item.get("description") or catalog_item.get("description") or "").strip(),
                "topic": normalize_topics(item.get("topic") or catalog_item.get("topic")),
            }
        )

    return resolved


def get_current_topic_index(state):
    return int(state.get("current_topic_index", 0) or 0)


def get_current_topic_turns(state):
    return int(state.get("current_topic_turns", 0) or 0)


def get_current_topic(state):
    topic = state.get("current_topic")
    if isinstance(topic, dict):
        return normalize_topic_entry(topic)
    topics = state.get("topics") or []
    index = get_current_topic_index(state)
    if 0 <= index < len(topics):
        return normalize_topic_entry(topics[index], index=index, lesson_name=state.get("lesson_name", ""))
    return {}


def get_checkpoint_indexes(state):
    return normalize_checkpoint_indexes(state.get("checkpoint_indexes"), len(state.get("topics") or []))


def is_checkpoint_topic(state, topic_index=None):
    if topic_index is None:
        topic_index = get_current_topic_index(state)
    return int(topic_index) in set(get_checkpoint_indexes(state))


def fallback_summary_update(state):
    summary = sanitize_summary(state.get("lesson_summary"))
    current_topic = get_current_topic(state)
    current_preview = build_topic_preview(current_topic, limit=100)
    next_preview = ""

    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)
    if current_index + 1 < len(topics):
        next_preview = build_topic_preview(topics[current_index + 1], limit=100)

    last_ai = latest_ai_message(state.get("messages"))
    if current_preview and last_ai and not is_done_response(last_ai):
        summary["taught_concepts"] = merge_note(summary["taught_concepts"], current_preview, max_items=8)

    last_user = latest_human_message(state.get("messages"))
    if last_user is not None:
        user_text = extract_text_content(last_user.content)
        user_note = build_topic_preview({"title": "", "content": user_text}, limit=100)
        if contains_any_hint(user_text, CONFUSION_HINTS) or "?" in user_text:
            summary["confusion"] = merge_note(summary["confusion"], user_note)
        elif contains_any_hint(user_text, UNDERSTOOD_HINTS):
            summary["understood"] = merge_note(summary["understood"], user_note)

    summary["next_to_teach"] = (
        ""
        if state.get("lesson_complete")
        else build_next_progress_note(
            current_preview,
            next_preview,
            waiting_for_student=bool(state.get("awaiting_reply")),
            topic_complete=bool(state.get("topic_complete")),
        )
    )
    return sanitize_summary(summary)


def update_running_summary(state):
    llm = get_llm(get_state_chat_model(state))
    current_topic = get_current_topic(state)
    current_preview = build_topic_preview(current_topic, limit=100)
    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)
    next_preview = ""
    if current_index + 1 < len(topics):
        next_preview = build_topic_preview(topics[current_index + 1], limit=100)

    recent_messages = trim_message_history(state.get("messages"), max_turns=2, max_chars=2200)
    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Update the running tutoring summary.\n"
            "Return only valid JSON with:\n"
            "taught_concepts: list[str]\n"
            "understood: list[str]\n"
            "confusion: list[str]\n"
            "next_to_teach: str\n"
            "Rules:\n"
            "- Keep items short and concrete.\n"
            "- Do not mention anything outside the given topic and conversation.\n"
            "- Capture only the most useful ongoing memory."
        ),
        user_prompt=(
            f"Previous summary:\n{json.dumps(sanitize_summary(state.get('lesson_summary')), ensure_ascii=False)}\n\n"
            f"Current topic:\n{json.dumps(current_topic, ensure_ascii=False)}\n\n"
            f"Next topic preview:\n{next_preview or 'None'}\n\n"
            f"Recent conversation:\n{build_message_transcript(recent_messages, include_tools=False)}"
        ),
    )

    summary = (
        merge_summaries(state.get("lesson_summary"), payload)
        if isinstance(payload, dict)
        else fallback_summary_update(state)
    )

    last_ai = latest_ai_message(state.get("messages"))
    if current_preview and last_ai and not is_done_response(last_ai):
        summary["taught_concepts"] = merge_note(summary["taught_concepts"], current_preview, max_items=8)

    if state.get("lesson_complete"):
        summary["next_to_teach"] = ""
    else:
        summary["next_to_teach"] = summary.get("next_to_teach") or build_next_progress_note(
            current_preview,
            next_preview,
            waiting_for_student=bool(state.get("awaiting_reply")),
            topic_complete=bool(state.get("topic_complete")),
        )

    return sanitize_summary(summary)


def should_advance_topic_with_llm(llm, state, latest_user_text):
    current_topic = get_current_topic(state)
    if not current_topic.get("content"):
        return False

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Decide if the tutor should move to the next lesson topic now.\n"
            "Return only valid JSON with:\n"
            "advance: bool\n"
            "Rules:\n"
            "- True if the student's latest message shows enough understanding, gives a reasonable conceptual answer, or clearly asks to continue.\n"
            "- If the tutor has already spent multiple turns on the same topic, prefer moving forward unless the student is still explicitly confused.\n"
            "- False if the student is confused, asking for clarification, or still discussing the same concept."
        ),
        user_prompt=(
            f"Current lesson summary:\n{json.dumps(sanitize_summary(state.get('lesson_summary')), ensure_ascii=False)}\n\n"
            f"Current topic:\n{json.dumps(current_topic, ensure_ascii=False)}\n\n"
            f"Recent conversation:\n{build_message_transcript(trim_message_history(state.get('messages'), max_turns=2, max_chars=1800), include_tools=False)}\n\n"
            f"Latest student message:\n{latest_user_text}"
        ),
    )

    if not isinstance(payload, dict):
        return False

    return bool(payload.get("advance"))


def should_advance_to_next_chunk(state):
    if state.get("lesson_complete"):
        return False
    if not state.get("awaiting_reply"):
        return False

    last_user = latest_human_message(state.get("messages"))
    if last_user is None:
        return False

    user_text = extract_text_content(last_user.content)
    normalized = normalize_text(user_text)
    current_topic_turns = get_current_topic_turns(state)
    if not normalized:
        return False

    if current_topic_turns >= MAX_TURNS_PER_TOPIC:
        return True
    if contains_any_hint(user_text, CONTINUE_HINTS):
        return True
    if contains_any_hint(user_text, CONFUSION_HINTS):
        return False
    if "?" in user_text and not contains_any_hint(user_text, UNDERSTOOD_HINTS):
        return False
    if contains_any_hint(user_text, UNDERSTOOD_HINTS):
        return True
    if len(tokenize(user_text)) >= 4:
        return should_advance_topic_with_llm(get_llm(get_state_chat_model(state)), state, user_text)
    return False


def plan_next_teaching_step(state):
    llm = get_llm(get_state_chat_model(state))
    current_topic = get_current_topic(state)
    current_turns = get_current_topic_turns(state)
    checkpoint_due = is_checkpoint_topic(state)
    recent_messages = trim_message_history(state.get("messages"), max_turns=2, max_chars=2200)
    content = str(current_topic.get("content") or "").strip()

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Plan the next micro-step for a Bangladeshi HSC physics tutor.\n"
            "Return only valid JSON with this schema:\n"
            '{\n'
            '  "next_focus": "string",\n'
            '  "remaining_after_this_reply": "string",\n'
            '  "topic_complete_after_reply": true,\n'
            '  "ask_checkpoint_now": false\n'
            '}\n'
            "Rules:\n"
            "- The tutor must teach the FULL topic over multiple short replies, not one long dump.\n"
            "- next_focus must be only the next small concept or one tightly related pair of ideas.\n"
            "- topic_complete_after_reply is true only if the next reply should finish the remaining untaught ideas for this topic.\n"
            "- ask_checkpoint_now is true only if checkpoint is due and the next reply should finish the topic before asking exactly one conceptual question.\n"
            "- Use the running summary and recent conversation to avoid repetition.\n"
            "- Do not skip concepts, but spread them across several replies."
        ),
        user_prompt=(
            f"Chapter: {state.get('chapter_name', '')}\n"
            f"Lesson: {state.get('lesson_name', '')}\n"
            f"Checkpoint due: {'yes' if checkpoint_due else 'no'}\n"
            f"Current topic turns already used: {current_turns} / {MAX_TURNS_PER_TOPIC}\n\n"
            f"Running summary:\n{json.dumps(sanitize_summary(state.get('lesson_summary')), ensure_ascii=False)}\n\n"
            f"Recent conversation:\n{build_message_transcript(recent_messages, include_tools=False)}\n\n"
            f"Current topic:\n{json.dumps(current_topic, ensure_ascii=False)}"
        ),
    )

    if not isinstance(payload, dict):
        payload = {}

    next_focus = str(payload.get("next_focus") or "").strip() or first_sentence(content, limit=140) or build_topic_preview(current_topic, limit=100)
    remaining_after_this_reply = str(payload.get("remaining_after_this_reply") or "").strip()
    topic_complete_after_reply = bool(payload.get("topic_complete_after_reply"))
    ask_checkpoint_now = bool(payload.get("ask_checkpoint_now")) and checkpoint_due

    if current_turns + 1 >= MAX_TURNS_PER_TOPIC:
        topic_complete_after_reply = True
    if ask_checkpoint_now and not topic_complete_after_reply:
        ask_checkpoint_now = False

    return {
        "next_focus": next_focus,
        "remaining_after_this_reply": remaining_after_this_reply,
        "topic_complete_after_reply": topic_complete_after_reply,
        "ask_checkpoint_now": ask_checkpoint_now,
    }


def build_current_teaching_prompt(state, teaching_plan=None):
    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)
    current_topic = get_current_topic(state)
    total = max(len(topics), 1)
    checkpoint_due = is_checkpoint_topic(state, current_index)
    figure_hints = extract_figure_hints(current_topic.get("content"))
    figure_line = ", ".join(figure_hints) if figure_hints else "none detected"
    teaching_plan = teaching_plan if isinstance(teaching_plan, dict) else {}
    next_focus = str(teaching_plan.get("next_focus") or "").strip() or build_topic_preview(current_topic, limit=100)
    remaining_after_this_reply = str(teaching_plan.get("remaining_after_this_reply") or "").strip() or "unknown"
    topic_complete_after_reply = bool(teaching_plan.get("topic_complete_after_reply"))
    ask_checkpoint_now = bool(teaching_plan.get("ask_checkpoint_now")) and checkpoint_due

    return (
        "You are a Bangladeshi HSC physics tutor. Teach the following topic to a student.\n\n"
        f"Chapter: {state.get('chapter_name', '')}\n"
        f"Lesson: {state.get('lesson_name', '')}\n"
        f"Topic {min(current_index + 1, total)} of {total}: {current_topic.get('title', '')}\n\n"
        "Rules:\n"
        "- Read the FULL topic content below carefully before replying\n"
        "- Explain every concept clearly using simple Bangla-friendly language across MULTIPLE small replies\n"
        "- Do NOT skip any part of the content overall, but do NOT cover the whole topic in one reply unless the plan says this reply should finish it\n"
        "- In this reply, teach only the next small concept or one tightly related pair of ideas\n"
        "- Use analogies and simplified examples to aid understanding\n"
        "- If the content mentions a চিত্র (diagram), call fetch_lesson_image with the চিত্র title as the hint. If an image is returned, describe what it shows in your own words to strengthen the explanation. Never paste the database description directly.\n"
        "- Keep this reply small: at most 3 short paragraphs and roughly 120-180 words unless a tiny extra clarification is necessary\n"
        f"- Checkpoint due for this topic: {'yes' if checkpoint_due else 'no'}\n"
        f"- Ask checkpoint question in this reply: {'yes' if ask_checkpoint_now else 'no'}\n"
        "- If checkpoint question in this reply is yes: after teaching, ask exactly ONE conceptual question\n"
        "- If checkpoint question in this reply is no: end the reply naturally without asking a question\n"
        f"- When the very last topic is complete: reply only with {DONE_TOKEN}\n"
        "- Never output raw URLs, markdown image tags, JSON, or tool details in the reply\n"
        f"- Running summary:\n{format_summary_for_prompt(state.get('lesson_summary'))}\n"
        f"- Next small concept to teach now: {next_focus}\n"
        f"- Topic will be complete after this reply: {'yes' if topic_complete_after_reply else 'no'}\n"
        f"- What should remain after this reply: {remaining_after_this_reply}\n"
        f"- Figure hints detected in the topic text: {figure_line}\n\n"
        "FULL TOPIC CONTENT:\n"
        f"{current_topic.get('content', '')}"
    )


def prepare_teach_messages(state, teaching_plan=None):
    recent_messages = trim_message_history(state.get("messages"))
    prompt = build_current_teaching_prompt(state, teaching_plan=teaching_plan)
    return [SystemMessage(content=prompt), *recent_messages]


def build_understanding_follow_up(state):
    current_topic = get_current_topic(state)
    topic_title = str(current_topic.get("title") or "এই topic").strip()
    key_line = first_sentence(current_topic.get("content"), limit=180)
    if key_line:
        return (
            f"আরেকবার সহজভাবে বলি। {key_line}\n\n"
            f"এখন নিজের ভাষায় বলো, {topic_title} এর মূল ধারণা কী?"
        ).strip()
    return f"আরেকবার সহজভাবে বলি। এখন নিজের ভাষায় বলো, {topic_title} এর মূল ধারণা কী?"


def select_topic(state: State):
    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)

    if state.get("lesson_complete") or current_index >= len(topics):
        summary = sanitize_summary(state.get("lesson_summary"), fallback_next="")
        summary["next_to_teach"] = ""
        return {
            "current_topic": {},
            "topic_complete": False,
            "pending_action": "",
            "lesson_complete": True,
            "awaiting_reply": False,
            "lesson_summary": summary,
        }

    current_topic = normalize_topic_entry(topics[current_index], index=current_index, lesson_name=state.get("lesson_name", ""))
    return {
        "current_topic": current_topic,
        "topic_complete": bool(state.get("topic_complete")),
        "pending_action": "",
    }


def teach(state: State):
    llm = get_llm(get_state_chat_model(state))
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(get_state_chat_model(state)))

    messages = ensure_message_ids(list(state.get("messages") or []), prefix="live")
    tool_images = extract_selected_images_from_tool_messages(messages)
    used_image_ids = merge_used_image_ids(state.get("used_image_ids"), tool_images)
    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)

    if state.get("lesson_complete") or current_index >= len(topics):
        summary = sanitize_summary(state.get("lesson_summary"), fallback_next="")
        summary["next_to_teach"] = ""
        return {
            "messages": [AIMessage(content=DONE_TOKEN)],
            "used_image_ids": used_image_ids,
            "topic_complete": True,
            "pending_action": "",
            "lesson_complete": True,
            "awaiting_reply": False,
            "lesson_summary": summary,
        }

    if state.get("awaiting_reply") and latest_human_message(messages) is not None:
        if state.get("topic_complete") and is_checkpoint_topic(state):
            return {
                "used_image_ids": used_image_ids,
                "pending_action": "check_understanding",
            }
        if state.get("topic_complete"):
            return {
                "used_image_ids": used_image_ids,
                "pending_action": "advance_topic",
            }

    teaching_plan = plan_next_teaching_step({**state, "messages": messages, "used_image_ids": used_image_ids})
    llm_with_tools = llm.bind_tools([fetch_lesson_image])
    prompt_messages = prepare_teach_messages(
        {**state, "messages": messages, "used_image_ids": used_image_ids},
        teaching_plan=teaching_plan,
    )
    response = invoke_llm_with_logging(
        llm_with_tools,
        prompt_messages,
        context="simple_graph.teach",
        metadata={
            "chat_model": get_state_chat_model(state),
            "chapter_name": state.get("chapter_name"),
            "lesson_name": state.get("lesson_name"),
            "topic_index": current_index,
        },
    )

    if getattr(response, "tool_calls", None):
        return {
            "messages": [response],
            "used_image_ids": used_image_ids,
            "pending_action": "",
        }

    lesson_complete = is_done_response(response)
    current_turns = get_current_topic_turns(state)
    if not lesson_complete:
        current_turns += 1
    topic_complete = bool(teaching_plan.get("topic_complete_after_reply")) or (
        not lesson_complete and current_turns >= MAX_TURNS_PER_TOPIC
    )
    pending_action = ""
    if topic_complete and not is_checkpoint_topic(state) and current_index == len(topics) - 1:
        pending_action = "advance_topic"

    next_state = {
        **state,
        "messages": [*messages, response],
        "used_image_ids": used_image_ids,
        "topic_complete": topic_complete,
        "lesson_complete": lesson_complete,
        "awaiting_reply": not lesson_complete,
    }
    summary = update_running_summary(next_state)

    return {
        "messages": [response],
        "used_image_ids": used_image_ids,
        "current_topic_turns": current_turns,
        "topic_complete": topic_complete,
        "pending_action": pending_action,
        "lesson_complete": lesson_complete,
        "awaiting_reply": not lesson_complete,
        "lesson_summary": summary,
    }


def route_after_teach(state: State):
    messages = state.get("messages") or []
    last_ai = latest_ai_message(messages)
    if isinstance(last_ai, AIMessage) and getattr(last_ai, "tool_calls", None):
        return "fetch_image"

    pending_action = str(state.get("pending_action") or "").strip()
    if pending_action in {"check_understanding", "advance_topic"}:
        return pending_action

    if state.get("lesson_complete") or is_done_response(last_ai):
        return "end"
    return "end"


def check_understanding(state: State):
    if not is_checkpoint_topic(state):
        return {"pending_action": "", "awaiting_reply": False}

    messages = ensure_message_ids(list(state.get("messages") or []), prefix="live")
    last_user = latest_human_message(messages)
    if last_user is None:
        return {"pending_action": "", "awaiting_reply": True}

    user_text = extract_text_content(last_user.content)
    llm = get_llm(get_state_chat_model(state))
    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "You are checking whether a Bangladeshi HSC physics student understood the current topic.\n"
            "Return only valid JSON with this schema:\n"
            '{ "understood": bool, "follow_up": str | null }\n'
            "Rules:\n"
            "- understood is true only if the student's latest reply is conceptually good enough to advance.\n"
            "- If understood is false, follow_up must contain a clearer re-explanation in simple Bangla-friendly language and then exactly one improved conceptual question.\n"
            "- If understood is true, follow_up must be null.\n"
            "- Use only the current topic content and the conversation.\n"
            "- Never output markdown fences."
        ),
        user_prompt=(
            f"Chapter: {state.get('chapter_name', '')}\n"
            f"Lesson: {state.get('lesson_name', '')}\n"
            f"Current topic:\n{json.dumps(get_current_topic(state), ensure_ascii=False)}\n\n"
            f"Current topic turns: {get_current_topic_turns(state)} / {MAX_TURNS_PER_TOPIC}\n\n"
            f"Recent conversation:\n{build_message_transcript(trim_message_history(messages, max_turns=2, max_chars=2200), include_tools=False)}\n\n"
            f"Latest student reply:\n{user_text}"
        ),
    )

    if not isinstance(payload, dict):
        payload = {
            "understood": should_advance_to_next_chunk(state),
            "follow_up": None if should_advance_to_next_chunk(state) else build_understanding_follow_up(state),
        }

    understood = bool(payload.get("understood"))
    forced_advance = get_current_topic_turns(state) >= MAX_TURNS_PER_TOPIC or should_advance_to_next_chunk(state)

    if understood or forced_advance:
        next_state = {
            **state,
            "messages": messages,
            "topic_complete": True,
            "awaiting_reply": False,
        }
        return {
            "topic_complete": True,
            "pending_action": "",
            "awaiting_reply": False,
            "lesson_summary": update_running_summary(next_state),
        }

    follow_up = str(payload.get("follow_up") or "").strip() or build_understanding_follow_up(state)
    response = AIMessage(content=follow_up)
    next_state = {
        **state,
        "messages": [*messages, response],
        "awaiting_reply": True,
    }

    return {
        "messages": [response],
        "current_topic_turns": get_current_topic_turns(state) + 1,
        "topic_complete": False,
        "pending_action": "",
        "awaiting_reply": True,
        "lesson_summary": update_running_summary(next_state),
    }


def route_after_check_understanding(state: State):
    if state.get("awaiting_reply"):
        return "end"
    return "advance_topic"


def advance_topic(state: State):
    if state.get("lesson_complete"):
        return {}

    topics = state.get("topics") or []
    current_index = get_current_topic_index(state)
    next_index = current_index + 1

    if next_index >= len(topics):
        summary = sanitize_summary(state.get("lesson_summary"), fallback_next="")
        summary["next_to_teach"] = ""
        return {
            "current_topic_index": next_index,
            "current_topic_turns": 0,
            "current_topic": {},
            "topic_complete": False,
            "pending_action": "",
            "lesson_complete": True,
            "awaiting_reply": False,
            "lesson_summary": summary,
        }

    next_topic = normalize_topic_entry(topics[next_index], index=next_index, lesson_name=state.get("lesson_name", ""))
    summary = sanitize_summary(state.get("lesson_summary"), fallback_next=build_topic_preview(next_topic))
    summary["next_to_teach"] = build_topic_preview(next_topic)

    return {
        "current_topic_index": next_index,
        "current_topic_turns": 0,
        "current_topic": next_topic,
        "topic_complete": False,
        "pending_action": "",
        "awaiting_reply": False,
        "lesson_summary": summary,
    }


builder = StateGraph(State)
builder.add_node("select_topic", select_topic)
builder.add_node("teach", teach)
builder.add_node("fetch_image", ToolNode([fetch_lesson_image]))
builder.add_node("check_understanding", check_understanding)
builder.add_node("advance_topic", advance_topic)
builder.add_edge(START, "select_topic")
builder.add_edge("select_topic", "teach")
builder.add_conditional_edges(
    "teach",
    route_after_teach,
    {
        "fetch_image": "fetch_image",
        "check_understanding": "check_understanding",
        "advance_topic": "advance_topic",
        "end": END,
    },
)
builder.add_edge("fetch_image", "teach")
builder.add_conditional_edges(
    "check_understanding",
    route_after_check_understanding,
    {
        "advance_topic": "advance_topic",
        "end": END,
    },
)
builder.add_edge("advance_topic", "select_topic")
graph = builder.compile(checkpointer=memory)


def get_thread_config(thread_id):
    return {"configurable": {"thread_id": thread_id}}


def delete_chat_thread(thread_id):
    try:
        memory.delete_thread(thread_id)
    except Exception:
        return False
    return True


def thread_has_live_state(thread_id):
    snapshot = graph.get_state(get_thread_config(thread_id))
    values = snapshot.values or {}
    return bool(values.get("topics"))


def clamp_topic_index(index, topics):
    if not topics:
        return 0
    try:
        parsed = int(index)
    except Exception:
        parsed = 0
    return max(0, min(parsed, len(topics)))


def build_initial_state_from_snapshot(chapter_name, lesson_name, topics, saved_thread_state, chat_model=None):
    if not isinstance(saved_thread_state, dict):
        return None

    expected_signature = compute_lesson_signature(topics)
    if saved_thread_state.get("chapter_name") != chapter_name:
        return None
    if saved_thread_state.get("lesson_name") != lesson_name:
        return None
    if saved_thread_state.get("lesson_signature") != expected_signature:
        return None

    recent_messages = deserialize_messages(saved_thread_state.get("recent_messages"))
    checkpoint_indexes = normalize_checkpoint_indexes(saved_thread_state.get("checkpoint_indexes"), len(topics))
    used_image_ids = normalize_used_image_ids(saved_thread_state.get("used_image_ids"))
    current_index = clamp_topic_index(saved_thread_state.get("current_topic_index", 0), topics)
    lesson_complete = bool(saved_thread_state.get("lesson_complete"))
    if lesson_complete:
        current_index = len(topics)

    current_topic = {}
    if not lesson_complete and current_index < len(topics):
        current_topic = normalize_topic_entry(topics[current_index], index=current_index, lesson_name=lesson_name)

    summary = sanitize_summary(saved_thread_state.get("lesson_summary"))
    if not lesson_complete and current_topic:
        next_preview = build_topic_preview(topics[current_index + 1], limit=100) if current_index + 1 < len(topics) else ""
        summary["next_to_teach"] = summary.get("next_to_teach") or build_next_teaching_note(
            build_topic_preview(current_topic, limit=100),
            next_preview,
            waiting_for_student=bool(saved_thread_state.get("awaiting_reply", saved_thread_state.get("awaiting_student_reply"))),
            topic_complete=bool(saved_thread_state.get("topic_complete")),
        )
    else:
        summary["next_to_teach"] = ""

    selected_chat_model = resolve_chat_model_id(chat_model or saved_thread_state.get("chat_model"))

    return {
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "chat_model": selected_chat_model,
        "topics": topics,
        "current_topic_index": current_index,
        "current_topic_turns": int(saved_thread_state.get("current_topic_turns", saved_thread_state.get("current_chunk_turns", 0)) or 0),
        "current_topic": current_topic,
        "topic_complete": bool(saved_thread_state.get("topic_complete")),
        "pending_action": "",
        "checkpoint_indexes": checkpoint_indexes,
        "used_image_ids": used_image_ids,
        "lesson_summary": summary,
        "awaiting_reply": bool(saved_thread_state.get("awaiting_reply", saved_thread_state.get("awaiting_student_reply"))),
        "lesson_complete": lesson_complete,
        "messages": trim_message_history(recent_messages),
    }


def build_initial_state_from_history(chapter_name, lesson_name, topics, history, chat_model=None):
    selected_chat_model = resolve_chat_model_id(chat_model)
    llm = get_llm(selected_chat_model)
    history_messages = build_history_messages(history)
    summary, current_index, lesson_complete = build_initial_thread_summary(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        topics=topics,
        history_messages=history_messages,
    )

    recent_messages = trim_message_history(history_messages)
    checkpoint_indexes = build_checkpoint_indexes(len(topics))
    awaiting_reply = bool(recent_messages) and not lesson_complete and isinstance(recent_messages[-1], AIMessage)
    current_topic = {}
    if not lesson_complete and current_index < len(topics):
        current_topic = normalize_topic_entry(topics[current_index], index=current_index, lesson_name=lesson_name)

    return {
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "chat_model": selected_chat_model,
        "topics": topics,
        "current_topic_index": current_index,
        "current_topic_turns": 1 if awaiting_reply else 0,
        "current_topic": current_topic,
        "topic_complete": False,
        "pending_action": "",
        "checkpoint_indexes": checkpoint_indexes,
        "used_image_ids": normalize_used_image_ids(collect_used_image_ids_from_history(history)),
        "lesson_summary": summary,
        "awaiting_reply": awaiting_reply,
        "lesson_complete": lesson_complete,
        "messages": recent_messages,
    }


def ensure_initial_thread_state(chapter_name, lesson_name, lesson_source, history, saved_thread_state, chat_model=None):
    topics = normalize_lesson_topics(lesson_source, fallback_lesson_name=lesson_name)
    if not topics:
        raise ValueError("Lesson topics are empty")

    snapshot_state = build_initial_state_from_snapshot(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        topics=topics,
        saved_thread_state=saved_thread_state,
        chat_model=chat_model,
    )
    if snapshot_state is not None:
        return snapshot_state

    return build_initial_state_from_history(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        topics=topics,
        history=history,
        chat_model=chat_model,
    )


def extract_turn_messages(all_messages, user_message_id):
    for index, message in enumerate(all_messages or []):
        if getattr(message, "id", None) == user_message_id:
            return list(all_messages[index:])
    return latest_turn_messages(all_messages)


def collect_turn_response_text(turn_messages):
    texts = []
    for message in turn_messages or []:
        if not isinstance(message, AIMessage):
            continue
        text = extract_text_content(message.content).strip()
        if text:
            texts.append(text)

    if not texts:
        return ""

    non_done = [text for text in texts if text.upper() != DONE_TOKEN]
    if non_done:
        return "\n\n".join(non_done).strip()
    return texts[-1]


def export_thread_state_snapshot(state):
    messages = ensure_message_ids(list(state.get("messages") or []), prefix="snap")
    topics = state.get("topics") or []
    return {
        "chapter_name": state.get("chapter_name", ""),
        "lesson_name": state.get("lesson_name", ""),
        "lesson_signature": compute_lesson_signature(topics),
        "chat_model": get_state_chat_model(state),
        "current_topic_index": get_current_topic_index(state),
        "current_topic_turns": get_current_topic_turns(state),
        "topic_complete": bool(state.get("topic_complete")),
        "used_image_ids": normalize_used_image_ids(state.get("used_image_ids")),
        "checkpoint_indexes": get_checkpoint_indexes(state),
        "lesson_summary": sanitize_summary(state.get("lesson_summary")),
        "awaiting_reply": bool(state.get("awaiting_reply")),
        "lesson_complete": bool(state.get("lesson_complete")),
        "recent_messages": serialize_messages(messages),
    }


def build_stateful_citations(chapter_name, lesson_name, lesson_catalog, history, user_text):
    if not isinstance(lesson_catalog, list) or not user_text:
        return []

    try:
        retrieval = retrieve_relevant_lesson_chunks(
            lesson_catalog,
            build_retrieval_query(user_text, history),
            current_lesson_name=lesson_name,
            top_k=1,
        )
    except Exception:
        return []

    return build_citations(chapter_name, lesson_name, retrieval)


def run_stateful_chat(
    thread_id,
    chapter_name,
    lesson_name,
    lesson_source,
    history,
    user_text,
    saved_thread_state=None,
    lesson_catalog=None,
    chat_model=None,
):
    selected_chat_model = resolve_chat_model_id(chat_model)
    llm = get_llm(selected_chat_model)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(selected_chat_model))

    config = get_thread_config(thread_id)
    user_message = HumanMessage(content=user_text, id=f"user-{uuid.uuid4()}")

    invoke_payload = {"messages": [user_message], "chat_model": selected_chat_model}
    if not thread_has_live_state(thread_id):
        invoke_payload = ensure_initial_thread_state(
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            lesson_source=lesson_source,
            history=history,
            saved_thread_state=saved_thread_state,
            chat_model=selected_chat_model,
        )
        invoke_payload["messages"] = [*invoke_payload.get("messages", []), user_message]

    try:
        state = graph.invoke(invoke_payload, config=config)
    except Exception as exc:
        raise ValueError(f"Chat generation failed: {exc}") from exc

    state = {**state, "chat_model": selected_chat_model}
    turn_messages = extract_turn_messages(state.get("messages") or [], user_message.id)
    response_text = collect_turn_response_text(turn_messages)
    current_topic = get_current_topic(state)

    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=extract_selected_images_from_tool_messages(turn_messages),
        response_text=response_text,
        current_topic=current_topic,
        chat_model=selected_chat_model,
    )
    updated_state = {
        **state,
        "used_image_ids": merge_used_image_ids(state.get("used_image_ids"), response_images),
    }

    citations = build_stateful_citations(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_catalog=lesson_catalog,
        history=history,
        user_text=user_text,
    )
    textbook_answer = response_text if citations else ""

    return {
        "response": response_text,
        "images": response_images,
        "thread_state": export_thread_state_snapshot(updated_state),
        "textbook_answer": textbook_answer,
        "extra_explanation": "",
        "citations": citations,
    }


def run_grounded_chat(thread_id, chapter_name, lesson_name, lesson_catalog, history, user_text, chat_model=None):
    del thread_id

    llm = get_llm(chat_model)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(chat_model))

    retrieval_query = build_retrieval_query(user_text, history)
    retrieval = retrieve_relevant_lesson_chunks(
        lesson_catalog,
        retrieval_query,
        current_lesson_name=lesson_name,
        top_k=3,
    )
    prompt = build_grounded_prompt(chapter_name, lesson_name, user_text, retrieval)
    messages = [SystemMessage(content=GROUNDING_SYSTEM_PROMPT)]
    messages.extend(build_grounded_history_messages(history))
    messages.append(HumanMessage(content=prompt))

    try:
        response = invoke_llm_with_logging(
            llm,
            messages,
            context="simple_graph.run_grounded_chat",
            metadata={
                "chat_model": resolve_chat_model_id(chat_model),
                "chapter_name": chapter_name,
                "lesson_name": lesson_name,
            },
        )
    except Exception as exc:
        raise ValueError(normalize_error_message(exc)) from exc

    parsed = parse_grounded_response(response.content)
    citations = build_citations(chapter_name, lesson_name, retrieval)
    fallback_markdown = compose_chat_markdown(
        parsed["textbook_answer"],
        parsed["extra_explanation"],
        citations,
    )

    return {
        "response": fallback_markdown,
        "images": [],
        "thread_state": {},
        "textbook_answer": parsed["textbook_answer"],
        "extra_explanation": parsed["extra_explanation"],
        "citations": citations,
    }


def run_chat(
    thread_id,
    chapter_name,
    lesson_name,
    lesson_source,
    history,
    user_text,
    saved_thread_state=None,
    lesson_catalog=None,
    chat_model=None,
):
    if isinstance(lesson_source, list) and lesson_catalog is None:
        return run_grounded_chat(
            thread_id,
            chapter_name,
            lesson_name,
            lesson_source,
            history,
            user_text,
            chat_model=chat_model,
        )

    return run_stateful_chat(
        thread_id=thread_id,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_source=lesson_source,
        history=history,
        user_text=user_text,
        saved_thread_state=saved_thread_state,
        lesson_catalog=lesson_catalog,
        chat_model=chat_model,
    )
