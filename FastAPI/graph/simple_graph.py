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
    from langgraph.graph import START, StateGraph
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
except (ImportError, ModuleNotFoundError):
    class BaseMessage:
        def __init__(self, content=None, id=None, name=None, **kwargs):
            del kwargs
            self.content = content
            self.id = id
            self.name = name

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

    START = object()

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


memory = MemorySaver()
lesson_image_loader = None

IMAGE_TOOL_NAME = "fetch_relevant_lesson_images"
MAX_RECENT_TURNS = 4
MAX_RECENT_MESSAGE_CHARS = 4500
MAX_SUMMARY_BATCH_CHARS = 2600
MAX_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 260
AUTO_IMAGE_MAX = 2
IMAGE_CANDIDATE_MAX = 5
MAX_HISTORY_ITEMS = 8

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
    r'(?<!\\)\\(?=(?:frac|int|sum|sqrt|cdot|times|left|right|vec|hat|theta|phi|pi|alpha|beta|gamma|lambda|mu|nu|rho|sigma|omega|Delta|delta|tau|sin|cos|tan|text|mathrm|mathbf|pm|quad|qquad|leq|geq|neq|approx)\b)'
)
LITERAL_NEWLINE_PATTERN = re.compile(r'\\n(?![A-Za-z])')
LITERAL_TAB_PATTERN = re.compile(r'\\t(?![A-Za-z])')

VISUAL_SUPPORT_HINTS = {
    "diagram",
    "figure",
    "graph",
    "image",
    "picture",
    "vector",
    "field line",
    "force line",
    "circuit",
    "ray",
    "চিত্র",
    "ডায়াগ্রাম",
    "ডায়াগ্রাম",
    "ছবি",
    "বলরেখা",
    "বর্তনী",
    "ভেক্টর",
    "রশ্মি",
    "গ্রাফ",
}

BASE_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "Teach in very simple Bangla-friendly language.\n"
    "Teach only one very small concept at a time.\n"
    "Use only the lesson material that is provided in the CURRENT LESSON CHUNK.\n"
    "Do not bring unrelated topics, extra formulas, or outside explanations.\n"
    "After explaining, ask one tiny conceptual question and wait for the student.\n"
    "If the student asks a question, answer it simply but stay inside the current lesson chunk.\n"
    "Use the same terminology and examples that appear in the lesson.\n"
    "When the lesson is fully covered, reply exactly: Done\n"
    "Only call fetch_relevant_lesson_images when a visual explanation would genuinely help.\n"
    "If images are shown, the UI will render them inside your reply bubble automatically.\n"
    "The system may also check the lesson image database after every reply and attach relevant visuals automatically.\n"
    "Do not get stuck on one chunk by asking very similar tiny questions again and again.\n"
    "Never output raw URLs, markdown image tags, JSON, or tool details in the reply."
)

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
    current_chunk_index: int
    lesson_summary: LessonSummary
    awaiting_student_reply: bool
    lesson_complete: bool
    current_chunk_turns: int
    recent_messages: list[dict[str, Any]]


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    chapter_name: str
    lesson_name: str
    lesson_chunks: list[str]
    current_chunk_index: int
    current_chunk_turns: int
    lesson_summary: LessonSummary
    awaiting_student_reply: bool
    lesson_complete: bool


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


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key, temperature=0)


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
        "image_id": image.get("image_id", ""),
        "description": str(image.get("description") or "").strip(),
        "topics": normalize_topics(image.get("topic")),
    }


def query_requests_visual(query_text):
    normalized = normalize_text(query_text)
    visual_words = [
        "diagram",
        "figure",
        "image",
        "picture",
        "graph",
        "draw",
        "চিত্র",
        "ডায়াগ্রাম",
        "ডায়াগ্রাম",
        "ছবি",
    ]
    return any(word in normalized for word in visual_words)


def chunk_needs_visual_support(text):
    normalized = normalize_text(text)
    return any(word in normalized for word in VISUAL_SUPPORT_HINTS)


def score_image_relevance(query_text, image):
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return 0

    description_tokens = tokenize(image.get("description"))
    topic_tokens = set()
    exact_topic_hits = 0

    for topic in image.get("topic") or []:
        topic_tokens.update(tokenize(topic))
        normalized_topic = normalize_text(topic)
        if normalized_topic and normalized_topic in normalize_text(query_text):
            exact_topic_hits += 1

    token_overlap = len(query_tokens & (description_tokens | topic_tokens))
    return token_overlap + (exact_topic_hits * 3)


def select_relevant_images(query_text, images, max_images):
    scored = []
    for image in images:
        score = score_image_relevance(query_text, image)
        if score > 0:
            scored.append((score, image))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    selected = [image for _, image in scored[:max_images]]

    if not selected and images and query_requests_visual(query_text):
        selected = images[:max_images]

    return selected


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


@tool(IMAGE_TOOL_NAME)
def fetch_relevant_lesson_images(chapter_name: str, lesson_name: str, query: str, max_images: int = 2) -> str:
    """Load lesson images from MongoDB and return compact metadata for the current explanation."""
    try:
        safe_max_images = max(1, min(int(max_images or 2), 4))
    except Exception:
        safe_max_images = 2

    images = load_images_from_database(chapter_name, lesson_name)
    if not images:
        return json.dumps(
            {
                "selected_images": [],
                "reason": "No images were found for this lesson.",
            },
            ensure_ascii=False,
        )

    selected_images = select_relevant_images(query_text=query, images=images, max_images=safe_max_images)
    compact_selected = [compact_image_metadata(image) for image in selected_images]

    return json.dumps(
        {
            "selected_images": compact_selected,
            "reason": (
                "Relevant images selected based on topic and description overlap."
                if compact_selected
                else "No relevant image matched this explanation."
            ),
        },
        ensure_ascii=False,
    )


def normalize_lesson_text(raw_lesson):
    if isinstance(raw_lesson, dict):
        text = raw_lesson.get("content") or raw_lesson.get("lesson_text") or raw_lesson.get("text") or ""
    else:
        text = str(raw_lesson or "").strip()
        parsed = parse_json_from_text(text)
        if isinstance(parsed, dict):
            extracted = parsed.get("content") or parsed.get("lesson_text") or parsed.get("text")
            if extracted:
                text = extracted

    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*\[Image[^\n]*\]\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long_unit(text, max_chars):
    cleaned = str(text or "").strip()
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[।.!?])\s+", cleaned)
    pieces = []
    buffer = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        candidate = sentence if not buffer else f"{buffer} {sentence}"
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            pieces.append(buffer.strip())
            buffer = ""

        if len(sentence) <= max_chars:
            buffer = sentence
            continue

        comma_parts = re.split(r"(?<=[,;:])\s+", sentence)
        sub_buffer = ""
        for part in comma_parts:
            part = part.strip()
            if not part:
                continue
            sub_candidate = part if not sub_buffer else f"{sub_buffer} {part}"
            if len(sub_candidate) <= max_chars:
                sub_buffer = sub_candidate
                continue
            if sub_buffer:
                pieces.append(sub_buffer.strip())
            sub_buffer = part
        if sub_buffer:
            pieces.append(sub_buffer.strip())

    if buffer:
        pieces.append(buffer.strip())

    return pieces


def is_heading_like(paragraph):
    text = str(paragraph or "").strip()
    if not text:
        return False
    if len(text) > 90:
        return False
    if re.search(r"[।.!?]", text):
        return False
    return True


def chunk_lesson_text(lesson_text, max_chunk_chars=MAX_CHUNK_CHARS, min_chunk_chars=MIN_CHUNK_CHARS):
    cleaned = normalize_lesson_text(lesson_text)
    if not cleaned:
        return []

    raw_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    units = []
    index = 0

    while index < len(raw_paragraphs):
        current = raw_paragraphs[index]
        if index + 1 < len(raw_paragraphs) and is_heading_like(current):
            current = f"{current}\n{raw_paragraphs[index + 1]}"
            index += 2
        else:
            index += 1

        if len(current) > max_chunk_chars:
            units.extend(split_long_unit(current, max_chunk_chars))
        else:
            units.append(current)

    chunks = []
    buffer = ""

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        candidate = unit if not buffer else f"{buffer}\n\n{unit}"
        if len(candidate) <= max_chunk_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(buffer.strip())
            buffer = ""

        if len(unit) <= max_chunk_chars:
            buffer = unit
            continue

        split_units = split_long_unit(unit, max_chunk_chars)
        for split_unit in split_units:
            if len(split_unit) >= min_chunk_chars:
                chunks.append(split_unit.strip())
            else:
                if chunks:
                    chunks[-1] = f"{chunks[-1]}\n\n{split_unit}".strip()
                else:
                    buffer = split_unit

    if buffer:
        chunks.append(buffer.strip())

    if not chunks and cleaned:
        return [cleaned[:max_chunk_chars].strip()]

    return chunks


def compute_lesson_signature(lesson_chunks):
    joined = "\n\n".join(lesson_chunks or [])
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def make_chunk_preview(chunk_text, limit=140):
    text = normalize_lesson_text(chunk_text)
    if not text:
        return ""

    first_line = text.splitlines()[0].strip()
    preview = first_line if first_line else text
    preview = re.sub(r"\s+", " ", preview).strip()

    if len(preview) <= limit:
        return preview
    return preview[: limit - 3].rstrip() + "..."


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


def build_next_teaching_note(current_chunk_preview, next_chunk_preview, waiting_for_student):
    if not current_chunk_preview and not next_chunk_preview:
        return ""
    if waiting_for_student and current_chunk_preview and next_chunk_preview:
        return f"{current_chunk_preview} বুঝেছে কি না নিশ্চিত করে তারপর {next_chunk_preview}"
    if waiting_for_student and current_chunk_preview:
        return f"{current_chunk_preview} বুঝেছে কি না নিশ্চিত করা"
    return next_chunk_preview or current_chunk_preview


def format_summary_for_prompt(summary):
    data = sanitize_summary(summary)
    sections = [
        f"Taught already: {', '.join(data['taught_concepts']) or 'nothing yet'}",
        f"Student understood: {', '.join(data['understood']) or 'not clear yet'}",
        f"Student confusion: {', '.join(data['confusion']) or 'none noted'}",
        f"What should happen next: {data['next_to_teach'] or 'teach the current chunk simply'}",
    ]
    return "\n".join(sections)


def build_history_image_notes(images):
    notes = []
    for image in normalize_images_for_response(images)[:2]:
        description = image.get("description")
        note = "Visual"
        if description:
            note += f": {description}"
        notes.append(note)
    return notes


def build_history_messages(history):
    messages = []
    for item in history or []:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = extract_text_content(item.get("content"))
        if role == "assistant":
            image_notes = build_history_image_notes(item.get("images") or [])
            if image_notes:
                content = f"{content}\n\n" + "\n".join(f"- {note}" for note in image_notes)

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


def normalize_images_for_response(raw_images):
    if not isinstance(raw_images, list):
        return []

    normalized = []
    for index, item in enumerate(raw_images):
        image = normalize_image_record(item, fallback_index=index)
        if image:
            normalized.append(
                {
                    "imageURL": image["imageURL"],
                    "description": image["description"],
                    "topic": image["topic"],
                }
            )

    return normalized


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


def remove_trimmed_messages(all_messages, kept_messages):
    kept_ids = {message.id for message in kept_messages if getattr(message, "id", None)}
    removals = []
    for message in all_messages or []:
        if getattr(message, "id", None) and message.id not in kept_ids:
            removals.append(RemoveMessage(id=message.id))
    return removals


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
    return extract_text_content(message.content) == "Done"


def contains_any_hint(text, hints):
    normalized = normalize_text(text)
    return any(hint in normalized for hint in hints)


def call_llm_for_json(llm, system_prompt, user_prompt):
    if llm is None:
        return None

    try:
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
    except Exception:
        return None

    return parse_json_from_text(extract_text_content(response.content))


def fallback_history_summary(messages, current_summary=None):
    summary = sanitize_summary(current_summary)

    for message in messages or []:
        if isinstance(message, AIMessage):
            note = make_chunk_preview(extract_text_content(message.content), limit=100)
            summary["taught_concepts"] = merge_note(summary["taught_concepts"], note, max_items=8)
        elif isinstance(message, HumanMessage):
            text = extract_text_content(message.content)
            short_note = make_chunk_preview(text, limit=100)
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


def infer_current_chunk_index_heuristic(lesson_chunks, summary, recent_messages):
    if not lesson_chunks:
        return 0

    summary_data = sanitize_summary(summary)
    next_hint = summary_data.get("next_to_teach", "")
    recent_text = build_message_transcript(recent_messages, include_tools=False, max_chars=1600)

    if next_hint:
        scores = []
        for index, chunk in enumerate(lesson_chunks):
            score = len(tokenize(next_hint) & tokenize(chunk))
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
    for index, chunk in enumerate(lesson_chunks):
        score = len(tokenize(combined_text) & tokenize(chunk))
        scores.append((score, index))

    scores.sort(reverse=True)
    if scores and scores[0][0] > 0:
        return min(scores[0][1], len(lesson_chunks) - 1)

    return 0


def infer_current_chunk_index(llm, chapter_name, lesson_name, lesson_chunks, summary, recent_messages):
    if not lesson_chunks:
        return 0, False

    last_ai = latest_ai_message(recent_messages)
    if is_done_response(last_ai):
        return len(lesson_chunks), True

    chunk_previews = "\n".join(
        f"{index}: {make_chunk_preview(chunk, limit=120)}"
        for index, chunk in enumerate(lesson_chunks)
    )

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Choose which lesson chunk should be active on the next tutoring turn.\n"
            "Return only valid JSON with:\n"
            "current_chunk_index: int\n"
            "lesson_complete: bool\n"
            "Rules:\n"
            "- Use 0-based chunk indexes.\n"
            "- If the lesson is already fully covered, set lesson_complete true.\n"
            "- Pick the chunk that the tutor should work with next."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Running summary:\n{json.dumps(sanitize_summary(summary), ensure_ascii=False)}\n\n"
            f"Recent conversation:\n{build_message_transcript(recent_messages, include_tools=False, max_chars=1800)}\n\n"
            f"Lesson chunk previews:\n{chunk_previews}"
        ),
    )

    if isinstance(payload, dict):
        try:
            index = int(payload.get("current_chunk_index", 0))
        except Exception:
            index = 0
        lesson_complete = bool(payload.get("lesson_complete"))
        index = max(0, min(index, len(lesson_chunks)))
        if lesson_complete:
            return len(lesson_chunks), True
        return min(index, len(lesson_chunks) - 1), False

    return infer_current_chunk_index_heuristic(lesson_chunks, summary, recent_messages), False


def build_initial_thread_summary(llm, chapter_name, lesson_name, lesson_chunks, history_messages):
    summary = summarize_older_conversation(llm, chapter_name, lesson_name, history_messages)
    recent_messages = trim_message_history(history_messages)
    index, lesson_complete = infer_current_chunk_index(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_chunks=lesson_chunks,
        summary=summary,
        recent_messages=recent_messages,
    )
    current_preview = make_chunk_preview(lesson_chunks[index], limit=100) if lesson_chunks and index < len(lesson_chunks) else ""
    next_preview = make_chunk_preview(lesson_chunks[index + 1], limit=100) if index + 1 < len(lesson_chunks) else ""
    summary["next_to_teach"] = (
        ""
        if lesson_complete
        else build_next_teaching_note(current_preview, next_preview, waiting_for_student=bool(recent_messages))
    )
    return sanitize_summary(summary), index, lesson_complete


def should_advance_chunk_with_llm(llm, state, latest_user_text):
    current_chunk = get_current_chunk_text(state)
    if not current_chunk:
        return False

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Decide if the tutor should move to the next lesson chunk now.\n"
            "Return only valid JSON with:\n"
            "advance: bool\n"
            "Rules:\n"
            "- True only if the student's latest message shows enough understanding or clearly asks to continue.\n"
            "- False if the student is confused, asking for clarification, or still discussing the same concept."
        ),
        user_prompt=(
            f"Current lesson summary:\n{json.dumps(sanitize_summary(state.get('lesson_summary')), ensure_ascii=False)}\n\n"
            f"Current chunk:\n{current_chunk}\n\n"
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
    if not state.get("awaiting_student_reply"):
        return False

    last_user = latest_human_message(state.get("messages"))
    if last_user is None:
        return False

    user_text = extract_text_content(last_user.content)
    normalized = normalize_text(user_text)
    current_chunk_turns = int(state.get("current_chunk_turns") or 0)
    if not normalized:
        return False

    if contains_any_hint(user_text, CONTINUE_HINTS):
        return True
    if contains_any_hint(user_text, CONFUSION_HINTS):
        return False
    if "?" in user_text and current_chunk_turns <= 1 and not contains_any_hint(user_text, CONTINUE_HINTS):
        return False
    if contains_any_hint(user_text, UNDERSTOOD_HINTS) and len(normalized) <= 120:
        return True
    if len(normalized.split()) <= 4 and normalized in {"হ্যাঁ", "জি", "ঠিক", "yes", "ok", "okay", "right"}:
        return True
    if current_chunk_turns >= 2 and len(normalized) <= 220 and "?" not in user_text:
        return True
    if current_chunk_turns >= 1 and len(normalized) <= 80 and "?" not in user_text:
        return True

    return should_advance_chunk_with_llm(get_llm(), state, user_text)


def get_current_chunk_text(state):
    lesson_chunks = state.get("lesson_chunks") or []
    current_index = int(state.get("current_chunk_index") or 0)
    if current_index < 0 or current_index >= len(lesson_chunks):
        return ""
    return lesson_chunks[current_index]


def lesson_has_visuals(chapter_name, lesson_name):
    return bool(load_images_from_database(chapter_name, lesson_name))


def build_current_teaching_prompt(state):
    lesson_chunks = state.get("lesson_chunks") or []
    current_index = int(state.get("current_chunk_index") or 0)
    current_chunk_turns = int(state.get("current_chunk_turns") or 0)
    current_chunk = get_current_chunk_text(state)
    total_chunks = len(lesson_chunks)
    summary_text = format_summary_for_prompt(state.get("lesson_summary"))
    has_visuals = lesson_has_visuals(state.get("chapter_name", ""), state.get("lesson_name", ""))

    return (
        f"{BASE_PROMPT}\n\n"
        f"Chapter: {state.get('chapter_name', '')}\n"
        f"Lesson: {state.get('lesson_name', '')}\n"
        f"Current step: {min(current_index + 1, max(total_chunks, 1))}/{max(total_chunks, 1)}\n"
        f"Teaching turns already spent on this chunk: {current_chunk_turns}\n"
        f"Visual aids available for this lesson: {'yes' if has_visuals else 'no'}\n"
        f"Running summary:\n{summary_text}\n\n"
        "Follow these turn rules:\n"
        "- Use only the CURRENT LESSON CHUNK below.\n"
        "- Keep the reply short and clear.\n"
        "- If this is the first teaching turn on this chunk, explain the chunk simply and ask one tiny conceptual question.\n"
        "- If you have already asked one tiny question on this chunk, do not ask another near-duplicate question.\n"
        "- On later turns of the same chunk, only clarify the student's doubt briefly. Do not loop on the same check-question.\n"
        "- If visual aids are available and the chunk is diagram-like, graph-like, line-like, vector-like, or notation-heavy, strongly prefer calling fetch_relevant_lesson_images on the first teaching turn.\n"
        "- If the student already answered the previous tiny question and you are on a new chunk, give a one-line bridge and teach the new chunk.\n"
        "- End with one tiny conceptual question unless you reply Done.\n\n"
        f"CURRENT LESSON CHUNK:\n{current_chunk}"
    )


def prepare_prompt_messages(state):
    recent_messages = trim_message_history(state.get("messages"))
    prompt = build_current_teaching_prompt(state)
    return [SystemMessage(content=prompt), *recent_messages]


def fallback_summary_update(state):
    summary = sanitize_summary(state.get("lesson_summary"))
    current_chunk = get_current_chunk_text(state)
    current_preview = make_chunk_preview(current_chunk, limit=100)
    next_chunk_preview = ""

    lesson_chunks = state.get("lesson_chunks") or []
    current_index = int(state.get("current_chunk_index") or 0)
    if current_index + 1 < len(lesson_chunks):
        next_chunk_preview = make_chunk_preview(lesson_chunks[current_index + 1], limit=100)

    last_ai = latest_ai_message(state.get("messages"))
    if current_preview and last_ai and not is_done_response(last_ai):
        summary["taught_concepts"] = merge_note(summary["taught_concepts"], current_preview, max_items=8)

    last_user = latest_human_message(state.get("messages"))
    if last_user is not None:
        user_text = extract_text_content(last_user.content)
        user_note = make_chunk_preview(user_text, limit=100)
        if contains_any_hint(user_text, CONFUSION_HINTS) or "?" in user_text:
            summary["confusion"] = merge_note(summary["confusion"], user_note)
        elif contains_any_hint(user_text, UNDERSTOOD_HINTS):
            summary["understood"] = merge_note(summary["understood"], user_note)

    summary["next_to_teach"] = (
        ""
        if state.get("lesson_complete")
        else build_next_teaching_note(current_preview, next_chunk_preview, waiting_for_student=True)
    )
    return sanitize_summary(summary)


def update_running_summary(state):
    llm = get_llm()
    current_chunk = get_current_chunk_text(state)
    current_preview = make_chunk_preview(current_chunk, limit=100)
    lesson_chunks = state.get("lesson_chunks") or []
    current_index = int(state.get("current_chunk_index") or 0)
    next_chunk_preview = ""
    if current_index + 1 < len(lesson_chunks):
        next_chunk_preview = make_chunk_preview(lesson_chunks[current_index + 1], limit=100)

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
            "- Do not mention anything outside the given chunk and conversation.\n"
            "- Capture only the most useful ongoing memory."
        ),
        user_prompt=(
            f"Previous summary:\n{json.dumps(sanitize_summary(state.get('lesson_summary')), ensure_ascii=False)}\n\n"
            f"Current chunk:\n{current_chunk}\n\n"
            f"Next chunk preview:\n{next_chunk_preview or 'None'}\n\n"
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
        summary["next_to_teach"] = summary.get("next_to_teach") or build_next_teaching_note(
            current_preview,
            next_chunk_preview,
            waiting_for_student=True,
        )

    return sanitize_summary(summary)


def advance_turn(state: State):
    if not should_advance_to_next_chunk(state):
        return {}

    lesson_chunks = state.get("lesson_chunks") or []
    current_index = int(state.get("current_chunk_index") or 0)
    next_index = current_index + 1

    if next_index >= len(lesson_chunks):
        summary = sanitize_summary(state.get("lesson_summary"), fallback_next="")
        summary["next_to_teach"] = ""
        return {
            "current_chunk_index": len(lesson_chunks),
            "current_chunk_turns": 0,
            "lesson_complete": True,
            "awaiting_student_reply": False,
            "lesson_summary": summary,
        }

    next_preview = make_chunk_preview(lesson_chunks[next_index], limit=100)
    summary = sanitize_summary(state.get("lesson_summary"), fallback_next=next_preview)
    summary["next_to_teach"] = next_preview
    return {
        "current_chunk_index": next_index,
        "current_chunk_turns": 0,
        "awaiting_student_reply": False,
        "lesson_summary": summary,
    }


def assistant(state: State):
    llm = get_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")

    if state.get("lesson_complete") or not get_current_chunk_text(state):
        return {
            "messages": [AIMessage(content="Done")],
            "awaiting_student_reply": False,
            "lesson_complete": True,
        }

    llm_with_tools = llm.bind_tools([fetch_relevant_lesson_images])
    prompt_messages = prepare_prompt_messages(state)
    response = llm_with_tools.invoke(prompt_messages)
    return {"messages": [response]}


def route_after_assistant(state: State):
    last_message = latest_ai_message(state.get("messages"))
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    return "postprocess"


def postprocess_turn(state: State):
    all_messages = ensure_message_ids(list(state.get("messages") or []), prefix="live")
    last_ai = latest_ai_message(all_messages)
    lesson_complete = state.get("lesson_complete", False) or is_done_response(last_ai)
    next_state = {**state, "messages": all_messages, "lesson_complete": lesson_complete}
    summary = update_running_summary(next_state)
    current_chunk_turns = int(state.get("current_chunk_turns") or 0)
    if last_ai is not None and not lesson_complete:
        current_chunk_turns += 1

    kept_messages = ensure_message_ids(trim_message_history(all_messages), prefix="live")
    removals = remove_trimmed_messages(all_messages, kept_messages)

    return {
        "lesson_summary": summary,
        "lesson_complete": lesson_complete,
        "awaiting_student_reply": False if lesson_complete else True,
        "current_chunk_turns": current_chunk_turns,
        "messages": removals,
    }


builder = StateGraph(State)
builder.add_node("advance_turn", advance_turn)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode([fetch_relevant_lesson_images]))
builder.add_node("postprocess", postprocess_turn)
builder.add_edge(START, "advance_turn")
builder.add_edge("advance_turn", "assistant")
builder.add_conditional_edges(
    "assistant",
    route_after_assistant,
    {
        "tools": "tools",
        "postprocess": "postprocess",
    },
)
builder.add_edge("tools", "assistant")
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
    return bool(values.get("lesson_chunks"))


def clamp_chunk_index(index, lesson_chunks):
    if not lesson_chunks:
        return 0
    try:
        parsed = int(index)
    except Exception:
        parsed = 0
    return max(0, min(parsed, len(lesson_chunks)))


def build_initial_state_from_snapshot(chapter_name, lesson_name, lesson_chunks, saved_thread_state):
    if not isinstance(saved_thread_state, dict):
        return None

    expected_signature = compute_lesson_signature(lesson_chunks)
    if saved_thread_state.get("chapter_name") != chapter_name:
        return None
    if saved_thread_state.get("lesson_name") != lesson_name:
        return None
    if saved_thread_state.get("lesson_signature") != expected_signature:
        return None

    recent_messages = deserialize_messages(saved_thread_state.get("recent_messages"))
    current_index = clamp_chunk_index(saved_thread_state.get("current_chunk_index", 0), lesson_chunks)
    lesson_complete = bool(saved_thread_state.get("lesson_complete"))
    if lesson_complete:
        current_index = len(lesson_chunks)

    summary = sanitize_summary(saved_thread_state.get("lesson_summary"))
    if not lesson_complete and current_index < len(lesson_chunks):
        current_preview = make_chunk_preview(lesson_chunks[current_index], limit=100)
        next_preview = make_chunk_preview(lesson_chunks[current_index + 1], limit=100) if current_index + 1 < len(lesson_chunks) else ""
        summary["next_to_teach"] = summary.get("next_to_teach") or build_next_teaching_note(
            current_preview,
            next_preview,
            waiting_for_student=bool(saved_thread_state.get("awaiting_student_reply")),
        )
    else:
        summary["next_to_teach"] = ""

    return {
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "lesson_chunks": lesson_chunks,
        "current_chunk_index": current_index,
        "current_chunk_turns": int(saved_thread_state.get("current_chunk_turns") or 0),
        "lesson_summary": summary,
        "awaiting_student_reply": bool(saved_thread_state.get("awaiting_student_reply")),
        "lesson_complete": lesson_complete,
        "messages": trim_message_history(recent_messages),
    }


def build_initial_state_from_history(chapter_name, lesson_name, lesson_chunks, history):
    llm = get_llm()
    history_messages = build_history_messages(history)
    summary, current_index, lesson_complete = build_initial_thread_summary(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_chunks=lesson_chunks,
        history_messages=history_messages,
    )

    recent_messages = trim_message_history(history_messages)
    return {
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "lesson_chunks": lesson_chunks,
        "current_chunk_index": current_index,
        "current_chunk_turns": 1 if recent_messages and not lesson_complete else 0,
        "lesson_summary": summary,
        "awaiting_student_reply": bool(recent_messages) and not lesson_complete,
        "lesson_complete": lesson_complete,
        "messages": recent_messages,
    }


def ensure_initial_thread_state(chapter_name, lesson_name, lesson_text, history, saved_thread_state):
    lesson_chunks = chunk_lesson_text(lesson_text)
    if not lesson_chunks:
        raise ValueError("Lesson content is empty")

    snapshot_state = build_initial_state_from_snapshot(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_chunks=lesson_chunks,
        saved_thread_state=saved_thread_state,
    )
    if snapshot_state is not None:
        return snapshot_state

    return build_initial_state_from_history(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_chunks=lesson_chunks,
        history=history,
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
        if not isinstance(payload, dict):
            continue

        for item in payload.get("selected_images") or []:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id") or "").strip()
            if not image_id or image_id in seen_ids:
                continue
            seen_ids.add(image_id)
            selected_images.append(
                {
                    "image_id": image_id,
                    "description": str(item.get("description") or "").strip(),
                    "topics": normalize_topics(item.get("topics")),
                }
            )

    return selected_images


def merge_selected_images(*groups, max_images=AUTO_IMAGE_MAX):
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
                    "description": str(item.get("description") or "").strip(),
                    "topics": normalize_topics(item.get("topics")),
                }
            )
            if len(merged) >= max_images:
                return merged

    return merged


def build_image_candidates_for_reply(chapter_name, lesson_name, response_text, user_text, current_chunk, tool_selected_images=None):
    images = load_images_from_database(chapter_name, lesson_name)
    if not images:
        return []

    primary_query = "\n".join(part for part in [response_text, user_text] if part).strip()
    fallback_query = "\n".join(part for part in [response_text, user_text, current_chunk] if part).strip()

    primary_matches = []
    fallback_matches = []

    if primary_query:
        primary_matches = [
            compact_image_metadata(image)
            for image in select_relevant_images(primary_query, images, IMAGE_CANDIDATE_MAX)
        ]

    if fallback_query:
        fallback_matches = [
            compact_image_metadata(image)
            for image in select_relevant_images(fallback_query, images, IMAGE_CANDIDATE_MAX)
        ]

    if not primary_matches and not fallback_matches:
        if chunk_needs_visual_support(current_chunk) or query_requests_visual(primary_query) or query_requests_visual(fallback_query):
            fallback_matches = [compact_image_metadata(image) for image in images[:AUTO_IMAGE_MAX]]

    return merge_selected_images(tool_selected_images, primary_matches, fallback_matches, max_images=IMAGE_CANDIDATE_MAX)


def fallback_inline_image_description(raw_description):
    text = re.sub(r"\s+", " ", str(raw_description or "").strip())
    if not text:
        return ""

    replacements = [
        (r"\bq1\b", "$q_1$"),
        (r"\bq2\b", "$q_2$"),
        (r"\bq3\b", "$q_3$"),
        (r"\bF\b", "$F$"),
        (r"\bE\b", "$E$"),
        (r"\bV\b", "$V$"),
        (r"\bI\b", "$I$"),
        (r"\br\b", "$r$"),
        (r"\bR\b", "$R$"),
        (r"\btheta\b", "$\\theta$"),
        (r"\balpha\b", "$\\alpha$"),
        (r"\bbeta\b", "$\\beta$"),
        (r"\bgamma\b", "$\\gamma$"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text[:220].strip()


def rewrite_image_descriptions_for_display(llm, chapter_name, lesson_name, response_text, current_chunk, selected_images):
    if not selected_images:
        return {}

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Rewrite lesson image captions for direct student display.\n"
            "Return only valid JSON with this shape:\n"
            '{"images":[{"image_id":"string","description":"string"}]}\n'
            "Rules:\n"
            "- Keep each description short: maximum 2 small sentences.\n"
            "- Use very simple Bangla-friendly wording.\n"
            "- Use LaTeX for symbols and notations when useful, for example $q_1$, $q_2$, $F$, $\\theta$.\n"
            "- Do not mention topics, metadata, or internal ids in the description.\n"
            "- Do not invent details that are not supported by the lesson chunk or the raw image description.\n"
            "- Output descriptions only, no markdown image tags."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Tutor response:\n{response_text}\n\n"
            f"Current lesson chunk:\n{current_chunk}\n\n"
            f"Images to rewrite:\n{json.dumps(selected_images, ensure_ascii=False)}"
        ),
    )

    rewritten = {}
    if isinstance(payload, dict):
        for item in payload.get("images") or []:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id") or "").strip()
            description = str(item.get("description") or "").strip()
            if image_id and description:
                rewritten[image_id] = description[:260].strip()

    return rewritten


def enhance_response_with_lesson_images(
    llm,
    chapter_name,
    lesson_name,
    user_text,
    response_text,
    current_chunk,
    candidate_images,
):
    if response_text == "Done" or not candidate_images:
        return {
            "response": response_text,
            "selected_images": [],
        }

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "You are improving a tutor reply after checking lesson images from the database.\n"
            "Return only valid JSON with this shape:\n"
            '{"response":"string","selected_images":[{"image_id":"string","description":"string"}]}\n'
            "Rules:\n"
            "- Select up to 2 images only if they genuinely help explain the current reply.\n"
            "- If no image helps, return selected_images as [].\n"
            "- If you select images, revise the response so it naturally references the visual, for example by saying to look at the figure below.\n"
            "- Keep the same simple Bangla-friendly tutoring style.\n"
            "- Stay strictly inside the original lesson chunk and original reply scope.\n"
            "- Do not add new concepts.\n"
            "- Each selected image description must be short, student-facing, and may use LaTeX notation like $q_1$, $F$, $\\theta$ when useful.\n"
            "- Do not mention image ids, topics, URLs, or database details.\n"
            "- The revised response should remain concise."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Student message:\n{user_text}\n\n"
            f"Current lesson chunk:\n{current_chunk}\n\n"
            f"Original tutor reply:\n{response_text}\n\n"
            f"Candidate lesson images:\n{json.dumps(candidate_images, ensure_ascii=False)}"
        ),
    )

    if not isinstance(payload, dict):
        return {
            "response": response_text,
            "selected_images": [],
        }

    revised_response = str(payload.get("response") or "").strip() or response_text
    selected_images = []
    seen_ids = set()

    for item in payload.get("selected_images") or []:
        if not isinstance(item, dict):
            continue
        image_id = str(item.get("image_id") or "").strip()
        if not image_id or image_id in seen_ids:
            continue
        seen_ids.add(image_id)
        selected_images.append(
            {
                "image_id": image_id,
                "description": str(item.get("description") or "").strip(),
                "topics": [],
            }
        )
        if len(selected_images) >= AUTO_IMAGE_MAX:
            break

    return {
        "response": revised_response,
        "selected_images": selected_images,
    }


def resolve_images_for_response(chapter_name, lesson_name, selected_images, response_text="", current_chunk=""):
    if not selected_images:
        return []

    rewritten_descriptions = {}
    needs_description_rewrite = any(not str(item.get("description") or "").strip() for item in selected_images)
    if needs_description_rewrite:
        llm = get_llm()
        rewritten_descriptions = rewrite_image_descriptions_for_display(
            llm=llm,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            response_text=response_text,
            current_chunk=current_chunk,
            selected_images=selected_images,
        )

    catalog = {
        image["image_id"]: image
        for image in load_images_from_database(chapter_name, lesson_name)
    }

    resolved = []
    for item in selected_images:
        catalog_item = catalog.get(item.get("image_id"))
        if not catalog_item:
            continue

        display_description = (
            str(item.get("description") or "").strip()
            or rewritten_descriptions.get(item.get("image_id"))
            or fallback_inline_image_description(item.get("description") or catalog_item["description"])
        )
        resolved.append(
            {
                "imageURL": catalog_item["imageURL"],
                "description": display_description,
                "topic": [],
            }
        )

    return resolved


def extract_turn_messages(all_messages, user_message_id):
    for index, message in enumerate(all_messages or []):
        if getattr(message, "id", None) == user_message_id:
            return list(all_messages[index:])
    return latest_turn_messages(all_messages)


def export_thread_state_snapshot(state):
    messages = ensure_message_ids(list(state.get("messages") or []), prefix="snap")
    lesson_chunks = state.get("lesson_chunks") or []
    return {
        "chapter_name": state.get("chapter_name", ""),
        "lesson_name": state.get("lesson_name", ""),
        "lesson_signature": compute_lesson_signature(lesson_chunks),
        "current_chunk_index": int(state.get("current_chunk_index") or 0),
        "current_chunk_turns": int(state.get("current_chunk_turns") or 0),
        "lesson_summary": sanitize_summary(state.get("lesson_summary")),
        "awaiting_student_reply": bool(state.get("awaiting_student_reply")),
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
    lesson_text,
    history,
    user_text,
    saved_thread_state=None,
    lesson_catalog=None,
):
    llm = get_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")

    config = get_thread_config(thread_id)
    user_message = HumanMessage(content=user_text, id=f"user-{uuid.uuid4()}")

    invoke_payload = {"messages": [user_message]}
    if not thread_has_live_state(thread_id):
        invoke_payload = ensure_initial_thread_state(
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            lesson_text=lesson_text,
            history=history,
            saved_thread_state=saved_thread_state,
        )
        invoke_payload["messages"] = [*invoke_payload.get("messages", []), user_message]

    try:
        state = graph.invoke(invoke_payload, config=config)
    except Exception as exc:
        raise ValueError(f"Chat generation failed: {exc}") from exc

    turn_messages = extract_turn_messages(state.get("messages") or [], user_message.id)
    last_ai = latest_ai_message(turn_messages) or latest_ai_message(state.get("messages"))
    response_text = extract_text_content(getattr(last_ai, "content", ""))
    current_chunk = get_current_chunk_text(state)

    tool_selected_images = extract_selected_images_from_tool_messages(turn_messages)
    candidate_images = build_image_candidates_for_reply(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        response_text=response_text,
        user_text=user_text,
        current_chunk=current_chunk,
        tool_selected_images=tool_selected_images,
    )

    enhanced = enhance_response_with_lesson_images(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        user_text=user_text,
        response_text=response_text,
        current_chunk=current_chunk,
        candidate_images=candidate_images,
    )

    response_text = str(enhanced.get("response") or "").strip() or response_text
    selected_images = enhanced.get("selected_images") or []
    if not selected_images:
        selected_images = tool_selected_images

    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=selected_images,
        response_text=response_text,
        current_chunk=current_chunk,
    )

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
        "thread_state": export_thread_state_snapshot(state),
        "textbook_answer": textbook_answer,
        "extra_explanation": "",
        "citations": citations,
    }


def run_grounded_chat(thread_id, chapter_name, lesson_name, lesson_catalog, history, user_text):
    del thread_id

    llm = get_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")

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
        response = llm.invoke(messages)
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
):
    if isinstance(lesson_source, list) and lesson_catalog is None:
        return run_grounded_chat(thread_id, chapter_name, lesson_name, lesson_source, history, user_text)

    return run_stateful_chat(
        thread_id=thread_id,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_text=lesson_source,
        history=history,
        user_text=user_text,
        saved_thread_state=saved_thread_state,
        lesson_catalog=lesson_catalog,
    )
