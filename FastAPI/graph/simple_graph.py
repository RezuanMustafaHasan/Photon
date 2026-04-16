import hashlib
import json
import os
import re

from typing import Any

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_core.tools import tool
    from langchain_groq import ChatGroq
except (ImportError, ModuleNotFoundError):
    class _BaseMessage:
        def __init__(self, content=None, **kwargs):
            del kwargs
            self.content = content

    class AIMessage(_BaseMessage):
        pass

    class HumanMessage(_BaseMessage):
        pass

    class SystemMessage(_BaseMessage):
        pass

    def tool(_name):
        def decorator(fn):
            return fn

        return decorator

    class ChatGroq:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def invoke(self, _messages):
            raise RuntimeError("ChatGroq is unavailable")

from graph.exam_generator import extract_json_text, normalize_error_message
from graph.lesson_grounding import (
    chunk_lesson_content,
    is_introductory_question,
    lesson_source_label,
    normalize_lesson_key,
    retrieve_relevant_lesson_chunks,
    truncate_text,
)
from graph.llm_logging import invoke_llm_with_logging


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
    "- If the student says things like start, begin, continue, পড়াও, শেখাও, or শুরু, treat that as a request to begin teaching the current lesson from the provided chunks.\n"
    "- For lesson-start requests, do not say the request is unclear and do not ask the student to restate the question.\n"
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
LESSON_FLOW_SYSTEM_PROMPT = (
    "You are a Bangladeshi HSC physics tutor teaching a lesson one topic at a time.\n"
    "You must respond in valid JSON only, with no markdown fences.\n"
    "Return this exact schema:\n"
    "{\n"
    '  "textbook_answer": "markdown teaching explanation grounded in the provided topic text",\n'
    '  "extra_explanation": "optional intuition or analogy",\n'
    '  "check_question": "one short conceptual question"\n'
    "}\n"
    "Rules:\n"
    "- Read the FULL topic content carefully before replying.\n"
    "- Use only the provided concept text.\n"
    "- Teach only this one topic. Do not jump to the next topic.\n"
    "- Explain the topic in enough detail to genuinely teach it, not as a one-line summary.\n"
    "- Cover all important ideas present in the topic content. Do not skip key points.\n"
    "- Use markdown structure, not plain text only.\n"
    "- Start textbook_answer with a short markdown heading for the current topic.\n"
    "- Use short bullets where they help clarity.\n"
    "- If the topic content contains a notation, equation, symbol, definition, or named rule, include it clearly.\n"
    "- Use simple Bangla-friendly language.\n"
    "- Use simplified examples or analogies when they help understanding.\n"
    "- Do not mention topic or lesson serial numbers like 2.6, 3.2, etc. Start directly with the idea.\n"
    "- check_question must be exactly one short conceptual question.\n"
    "- Do not say the request is unclear.\n"
    "- When writing formulas or symbols, always use Markdown math delimiters: inline $...$ and block $$...$$."
)
UNDERSTANDING_CHECK_SYSTEM_PROMPT = (
    "You evaluate whether a Bangladeshi HSC physics student understood the last taught concept.\n"
    "You must respond in valid JSON only, with no markdown fences.\n"
    "Return this exact schema:\n"
    "{\n"
    '  "understood": true,\n'
    '  "reason": "short reason"\n'
    "}\n"
    "Rules:\n"
    "- If the student clearly says yes, fine, okay, understood, বোঝেছি, হ্যাঁ, জি, or gives a correct short answer, set understood to true.\n"
    "- If the student says they are confused, says no, or asks for clarification on the same concept, set understood to false.\n"
    "- Be lenient with short affirmative replies."
)
IMAGE_TOOL_NAME = "fetch_lesson_image"
MAX_HISTORY_ITEMS = 8
DEFAULT_CHAT_MODEL = "groq:openai/gpt-oss-120b"
DEFAULT_CHAT_MODEL_CONFIG = {
    "id": DEFAULT_CHAT_MODEL,
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
}
INVALID_JSON_BACKSLASH_PATTERN = re.compile(r'(?<!\\)\\(?!["\\/bfnrtu])')
LATEX_COMMAND_BACKSLASH_PATTERN = re.compile(
    r"(?<!\\)\\(?=(?:frac|int|sum|sqrt|cdot|times|left|right|vec|hat|theta|phi|pi|alpha|beta|gamma|lambda|mu|nu|rho|sigma|omega|Delta|delta|tau|sin|cos|tan|text|mathrm|mathbf|pm|quad|qquad|leq|geq|neq|approx)\b)"
)
LITERAL_NEWLINE_PATTERN = re.compile(r"\\n(?![A-Za-z])")
LITERAL_TAB_PATTERN = re.compile(r"\\t(?![A-Za-z])")
TOPIC_NUMBER_PREFIX_PATTERN = re.compile(r"^\s*[০-৯0-9]+(?:\s*[.\-:]\s*[০-৯0-9]+)*\s*[:।.-]?\s*")
FIGURE_TITLE_PATTERN = re.compile(r"চিত্র(?:\s*[০-৯0-9]+(?:\.[০-৯0-9]+)*)?\s*[:：-]\s*([^\n\r]+)")
FIGURE_LINE_PATTERN = re.compile(r"([^\n\r]*চিত্র[^\n\r]*)")
POSITIVE_UNDERSTANDING_PHRASES = {
    "fine",
    "ok",
    "okay",
    "yes",
    "yep",
    "got it",
    "understood",
    "clear",
    "continue",
    "next",
    "বোঝেছি",
    "বুঝেছি",
    "বুঝতে পেরেছি",
    "হ্যাঁ",
    "হ্যা",
    "জি",
    "জী",
    "ঠিক আছে",
    "ঠিকাছে",
    "আচ্ছা",
    "bujhsi",
    "bujhchi",
    "bujsi",
    "bujhlam",
    "bivob",
    "potential",
}
NEGATIVE_UNDERSTANDING_PHRASES = {
    "no",
    "not clear",
    "dont understand",
    "don't understand",
    "confused",
    "again",
    "bujhini",
    "bujhte parini",
    "বুঝিনি",
    "বুঝতে পারিনি",
    "না",
    "আবার বলুন",
    "আবার বলেন",
    "ক্লিয়ার না",
    "clear না",
}
ROMANIZED_TO_BANGLA_HINTS = {
    "bivob": "বিভব",
    "potential": "বিভব",
    "bolrekha": "বলরেখা",
    "field": "ক্ষেত্র",
    "charge": "আধান",
    "bol": "বল",
    "shoman": "সমান",
    "dhonatmak": "ধনাত্মক",
    "rinatmak": "ঋণাত্মক",
}

lesson_image_loader = None


def configure_image_loader(loader):
    global lesson_image_loader
    lesson_image_loader = loader


def delete_chat_thread(thread_id):
    del thread_id
    return True


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


def normalize_grounded_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = LITERAL_NEWLINE_PATTERN.sub("\n", text)
    text = LITERAL_TAB_PATTERN.sub(" ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def collapse_inline_whitespace(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_topic_numbering(value):
    text = collapse_inline_whitespace(value)
    stripped = TOPIC_NUMBER_PREFIX_PATTERN.sub("", text).strip()
    return stripped or text


def repair_invalid_json_backslashes(value):
    text = str(value or "")
    text = LATEX_COMMAND_BACKSLASH_PATTERN.sub(r"\\\\", text)
    return INVALID_JSON_BACKSLASH_PATTERN.sub(r"\\\\", text)


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


def call_llm_for_json(llm, system_prompt, user_prompt, context):
    if llm is None:
        return None

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        response = invoke_llm_with_logging(llm, messages, context=context)
    except Exception:
        return None

    return parse_json_from_text(extract_text_content(response.content))


def normalize_used_image_ids(value):
    if not isinstance(value, list):
        return []
    seen = set()
    normalized = []
    for item in value:
        image_id = str(item or "").strip()
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        normalized.append(image_id)
    return normalized


def merge_used_image_ids(existing, new_ids):
    merged = normalize_used_image_ids(existing)
    seen = set(merged)
    for item in normalize_used_image_ids(new_ids):
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def compose_chat_markdown(textbook_answer, extra_explanation, citations, check_question=""):
    textbook_answer = normalize_grounded_text(textbook_answer)
    extra_explanation = normalize_grounded_text(extra_explanation)
    check_question = normalize_grounded_text(check_question)
    del citations

    parts = []
    if textbook_answer:
        parts.append(textbook_answer)
    if extra_explanation:
        parts.append(extra_explanation)
    if check_question:
        parts.append(f"ছোট প্রশ্ন: {check_question}")

    return "\n\n".join(part for part in parts if part).strip()


def assistant_history_text(item):
    content = str(item.get("content") or "").strip()
    if content:
        return content

    textbook_answer = str(item.get("textbook_answer") or "").strip()
    extra_explanation = str(item.get("extra_explanation") or "").strip()
    citations = item.get("citations") if isinstance(item.get("citations"), list) else []
    check_question = str(item.get("check_question") or "").strip()
    return compose_chat_markdown(textbook_answer, extra_explanation, citations, check_question=check_question)


def build_history_messages(history):
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
    user_text = str(user_text or "").strip()
    if is_introductory_question(user_text):
        return user_text

    context_parts = [user_text]
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

    if retrieval_mode == "intro":
        return (
            f"Current lesson:\n"
            f"- Chapter: {chapter_name}\n"
            f"- Lesson: {lesson_name}\n"
            f"- Best matching lesson: {source_lesson_name}\n"
            f"- Retrieval mode: {retrieval_mode}\n\n"
            "The student is asking to start or continue this lesson, not asking a specific question.\n"
            "Use the retrieved lesson chunks below to begin teaching the current lesson naturally.\n"
            "In textbook_answer, give a short lesson opening and explain the first important ideas from these chunks in simple, student-friendly language.\n"
            "Do not say the request is unclear.\n"
            "Keep textbook_answer grounded only in the retrieved lesson chunks.\n"
            "Use extra_explanation only for a small intuition, analogy, or clarification if it helps.\n\n"
            f"Retrieved lesson chunks:\n{context_block}\n\n"
            f"Student message:\n{user_text}"
        )

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


def parse_teaching_response(raw_content):
    raw_output = extract_text_content(raw_content)
    json_text = repair_invalid_json_backslashes(extract_json_text(raw_output))

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The lesson flow JSON is malformed: {exc.msg}.") from exc

    if not isinstance(payload, dict):
        raise ValueError("The lesson flow payload must be a JSON object.")

    textbook_answer = normalize_grounded_text(payload.get("textbook_answer") or "")
    extra_explanation = normalize_grounded_text(payload.get("extra_explanation") or "")
    check_question = normalize_grounded_text(payload.get("check_question") or payload.get("question") or "")

    if not textbook_answer:
        raise ValueError("The lesson flow payload must contain a textbook_answer.")
    if not check_question:
        raise ValueError("The lesson flow payload must contain a check_question.")

    return {
        "textbook_answer": textbook_answer,
        "extra_explanation": extra_explanation,
        "check_question": check_question,
    }


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def normalize_lesson_flow_state(saved_thread_state):
    state = saved_thread_state if isinstance(saved_thread_state, dict) else {}
    return {
        "mode": str(state.get("mode") or "").strip(),
        "concept_index": max(0, safe_int(state.get("concept_index"), 0)),
        "current_step_index": max(0, safe_int(state.get("current_step_index"), safe_int(state.get("concept_index"), 0))),
        "awaiting_understanding": bool(state.get("awaiting_understanding")),
        "lesson_complete": bool(state.get("lesson_complete")),
        "last_question": str(state.get("last_question") or "").strip(),
        "used_image_ids": normalize_used_image_ids(state.get("used_image_ids")),
    }


def clean_figure_hint(value):
    text = collapse_inline_whitespace(value)
    text = re.sub(r"[।.:\-–—\s]+$", "", text).strip()
    return strip_topic_numbering(text)


def extract_figure_hints(value):
    text = normalize_grounded_text(value)
    if "চিত্র" not in text:
        return []

    hints = []
    seen = set()
    for match in FIGURE_TITLE_PATTERN.finditer(text):
        hint = clean_figure_hint(match.group(1))
        if hint and hint not in seen:
            seen.add(hint)
            hints.append(hint)

    if hints:
        return hints

    for match in FIGURE_LINE_PATTERN.finditer(text):
        line = clean_figure_hint(match.group(1))
        if line and line not in seen:
            seen.add(line)
            hints.append(line)
    return hints


def get_current_lesson_entry(lesson_catalog, lesson_name):
    entries = lesson_catalog if isinstance(lesson_catalog, list) else []
    current_key = normalize_lesson_key(lesson_name)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if normalize_lesson_key(entry.get("lesson_name")) == current_key:
            return entry
    return entries[0] if entries else None


def build_lesson_concepts(lesson_catalog, lesson_name, lesson_source=None):
    if isinstance(lesson_source, dict) and isinstance(lesson_source.get("topics"), list):
        concepts = []
        for index, topic in enumerate(lesson_source.get("topics") or [], start=1):
            if not isinstance(topic, dict):
                continue
            chunk_text = str(topic.get("content") or topic.get("text") or "").strip()
            if not chunk_text:
                continue
            concepts.append(
                {
                    "concept_index": len(concepts),
                    "display_index": index,
                    "section_label": strip_topic_numbering(
                        topic.get("title") or topic.get("topic_title") or topic.get("name") or f"Concept {index}"
                    ),
                    "chunk_text": chunk_text,
                }
            )
        if concepts:
            return concepts

    lesson_entry = get_current_lesson_entry(lesson_catalog, lesson_name)
    if not isinstance(lesson_entry, dict):
        return []

    concepts = []
    for index, chunk in enumerate(chunk_lesson_content(lesson_entry.get("content")), start=1):
        chunk_text = str(chunk.get("chunk_text") or "").strip()
        if not chunk_text:
            continue
        concepts.append(
            {
                "concept_index": len(concepts),
                "display_index": index,
                "section_label": strip_topic_numbering(chunk.get("section_label") or f"Concept {index}"),
                "chunk_text": chunk_text,
            }
        )
    return concepts


def build_lesson_flow_prompt(
    chapter_name,
    lesson_name,
    concept,
    student_reply="",
    previous_question="",
    re_explain=False,
):
    action_line = (
        "The student did not clearly show understanding yet. Re-explain the same topic more simply and more clearly, then ask one new short conceptual question."
        if re_explain
        else "Teach this topic clearly and with enough detail, then ask one short conceptual question."
    )
    follow_up_block = ""
    if re_explain:
        follow_up_block = (
            f"Previous check question:\n{previous_question}\n\n"
            f"Student reply:\n{student_reply}\n\n"
        )

    figure_hints = extract_figure_hints(concept.get("chunk_text"))
    figure_block = ""
    if figure_hints:
        figure_block = "Figure hints mentioned inside this topic:\n"
        figure_block += "\n".join(f"- {hint}" for hint in figure_hints)
        figure_block += "\n\n"

    return (
        f"Chapter: {chapter_name}\n"
        f"Lesson: {lesson_name}\n"
        f"Topic title: {strip_topic_numbering(concept.get('section_label'))}\n\n"
        f"{action_line}\n"
        "Give a solid teaching explanation for this topic in this turn.\n"
        "Explain all important parts of this topic clearly, but do not move to the next topic.\n"
        "Use markdown headings and, when helpful, short bullets.\n"
        "If the topic includes notation, symbols, equations, or definitions, include them clearly.\n"
        "Do not repeat any lesson number or serial number such as 2.6 or 3.2.\n"
        "If a figure is mentioned, use that idea naturally while explaining.\n\n"
        f"{follow_up_block}"
        f"{figure_block}"
        f"Full topic content:\n{concept.get('chunk_text')}"
    )


def normalize_joined_text(value):
    return re.sub(r"\s+", "", normalize_text(value))


def romanized_keyword_match(student_reply, concept):
    reply_text = normalize_text(student_reply)
    if not reply_text:
        return False

    concept_text = normalize_text(concept.get("chunk_text"))
    section_text = normalize_text(concept.get("section_label"))
    haystack = f"{section_text}\n{concept_text}"
    for romanized, bangla_hint in ROMANIZED_TO_BANGLA_HINTS.items():
        if romanized in reply_text and bangla_hint in haystack:
            return True
    return False


def classify_understanding_reply(user_text):
    normalized = normalize_text(user_text)
    joined = normalize_joined_text(user_text)
    if not normalized:
        return False

    if normalized in POSITIVE_UNDERSTANDING_PHRASES or joined in {normalize_joined_text(item) for item in POSITIVE_UNDERSTANDING_PHRASES}:
        return True
    if normalized in NEGATIVE_UNDERSTANDING_PHRASES or joined in {normalize_joined_text(item) for item in NEGATIVE_UNDERSTANDING_PHRASES}:
        return False

    for phrase in POSITIVE_UNDERSTANDING_PHRASES:
        if phrase and phrase in normalized:
            return True
    for phrase in NEGATIVE_UNDERSTANDING_PHRASES:
        if phrase and phrase in normalized:
            return False
    return None


def short_non_negative_reply(user_text):
    normalized = normalize_text(user_text)
    if not normalized:
        return False
    if any(phrase in normalized for phrase in NEGATIVE_UNDERSTANDING_PHRASES):
        return False
    if "?" in user_text:
        return False
    token_count = len(re.findall(r"[a-z0-9\u0980-\u09ff]+", normalized))
    return 0 < token_count <= 4


def assess_understanding_reply(llm, chapter_name, lesson_name, concept, previous_question, student_reply):
    heuristic = classify_understanding_reply(student_reply)
    if heuristic is not None:
        return heuristic

    if romanized_keyword_match(student_reply, concept) and short_non_negative_reply(student_reply):
        return True

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=UNDERSTANDING_CHECK_SYSTEM_PROMPT,
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n"
            f"Section: {concept.get('section_label')}\n\n"
            f"Concept text:\n{concept.get('chunk_text')}\n\n"
            f"Check question:\n{previous_question}\n\n"
            f"Student reply:\n{student_reply}"
        ),
        context="simple_graph.assess_understanding_reply",
    )
    if isinstance(payload, dict) and isinstance(payload.get("understood"), bool):
        return payload["understood"]
    return short_non_negative_reply(student_reply)


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
    if not query_tokens:
        return 0

    description_tokens = tokenize(image.get("description"))
    topic_tokens = set()
    for topic in image.get("topic") or []:
        topic_tokens.update(tokenize(topic))

    overlap = len(query_tokens & (description_tokens | topic_tokens))
    normalized_query = normalize_text(query_text)
    normalized_description = normalize_text(image.get("description"))
    if normalized_query and normalized_query in normalized_description:
        overlap += 2
    return overlap


def find_best_lesson_image(chapter_name, lesson_name, hint, used_image_ids=None):
    images = load_images_from_database(chapter_name, lesson_name)
    excluded = {str(item).strip() for item in used_image_ids or [] if str(item).strip()}

    best_image = None
    best_score = 0
    for image in images:
        image_id = str(image.get("image_id") or "").strip()
        if not image_id or image_id in excluded:
            continue
        score = score_image_relevance(hint, image)
        if score > best_score:
            best_score = score
            best_image = image

    if best_image is None or best_score <= 0:
        return None
    return {
        "image_id": best_image["image_id"],
        "imageURL": best_image["imageURL"],
        "description": best_image["description"],
        "topic": best_image["topic"],
    }


@tool(IMAGE_TOOL_NAME)
def fetch_lesson_image(chapter_name: str, lesson_name: str, hint: str) -> str:
    """
    Search lesson images using a hint from the reply context.
    Reads lesson image descriptions and returns the best matching image.
    """
    image = find_best_lesson_image(chapter_name, lesson_name, hint)
    if image is None:
        return json.dumps({"found": False}, ensure_ascii=False)

    return json.dumps(
        {
            "found": True,
            "image_id": image["image_id"],
            "imageURL": image["imageURL"],
            "description": image["description"],
        },
        ensure_ascii=False,
    )


def fallback_inline_image_description(raw_description):
    text = re.sub(r"\s+", " ", str(raw_description or "").strip())
    if not text:
        return ""
    text = text[:200].strip()
    if text.endswith("."):
        text = text[:-1].rstrip()
    return text


def manual_rewrite_image_description(raw_description):
    text = fallback_inline_image_description(raw_description)
    if not text:
        return ""
    if re.search(r"[\u0980-\u09ff]", text):
        return f"এই ছবিতে {text.rstrip('।.') } দেখানো হয়েছে।"
    return f"এই ছবিতে {text} দেখানো হয়েছে।"


def rewrite_image_description_for_display(llm, chapter_name, lesson_name, response_text, image):
    if llm is None or not isinstance(image, dict):
        return ""

    payload = call_llm_for_json(
        llm=llm,
        system_prompt=(
            "Rewrite a lesson image caption for a Bangladeshi HSC physics student.\n"
            "Return only valid JSON with this schema:\n"
            '{ "description": "string" }\n'
            "Rules:\n"
            "- Write in simple Bangla-friendly language.\n"
            "- Do not copy the raw database description verbatim.\n"
            "- Keep it short: one or two short sentences.\n"
            "- Describe what the image likely shows in support of the tutor reply.\n"
            "- Do not mention URLs, ids, database fields, or metadata."
        ),
        user_prompt=(
            f"Chapter: {chapter_name}\n"
            f"Lesson: {lesson_name}\n\n"
            f"Tutor reply:\n{response_text}\n\n"
            f"Raw image metadata:\n{json.dumps(image, ensure_ascii=False)}"
        ),
        context="simple_graph.rewrite_image_description_for_display",
    )

    if not isinstance(payload, dict):
        return ""

    description = str(payload.get("description") or "").strip()
    raw_description = str(image.get("description") or "").strip()
    if not description or normalize_text(description) == normalize_text(raw_description):
        return ""
    return description


def resolve_images_for_response(
    chapter_name,
    lesson_name,
    selected_images,
    response_text="",
    current_topic=None,
    chat_model=None,
):
    del current_topic

    if not selected_images:
        return []

    catalog = {
        image["image_id"]: image
        for image in load_images_from_database(chapter_name, lesson_name)
    }
    llm = get_llm(chat_model)
    resolved = []
    for item in selected_images:
        image_id = str(item.get("image_id") or "").strip()
        if not image_id:
            continue

        catalog_item = catalog.get(image_id, {})
        image_url = str(item.get("imageURL") or catalog_item.get("imageURL") or "").strip()
        if not image_url:
            continue

        raw_description = str(item.get("description") or catalog_item.get("description") or "").strip()
        rewritten = rewrite_image_description_for_display(
            llm=llm,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            response_text=response_text,
            image={
                "image_id": image_id,
                "description": raw_description,
                "topic": normalize_topics(item.get("topic") or catalog_item.get("topic")),
            },
        )
        display_description = rewritten or manual_rewrite_image_description(raw_description) or fallback_inline_image_description(raw_description)
        resolved.append(
            {
                "image_id": image_id,
                "imageURL": image_url,
                "description": display_description,
                "topic": normalize_topics(item.get("topic") or catalog_item.get("topic")),
            }
        )

    return resolved


def extract_lesson_text(lesson_source, fallback_lesson_name=""):
    if isinstance(lesson_source, str):
        return lesson_source.strip()

    if not isinstance(lesson_source, dict):
        return ""

    content = str(lesson_source.get("content") or lesson_source.get("lesson_text") or lesson_source.get("text") or "").strip()
    if content:
        return content

    parts = []
    for topic in lesson_source.get("topics") or []:
        if not isinstance(topic, dict):
            continue
        title = str(topic.get("title") or topic.get("topic_title") or topic.get("name") or "").strip()
        topic_content = str(topic.get("content") or topic.get("text") or "").strip()
        if title:
            parts.append(title)
        if topic_content:
            parts.append(topic_content)

    if parts:
        return "\n\n".join(parts).strip()

    lesson_name = (
        str(lesson_source.get("lesson_name") or lesson_source.get("lesson_name_bn") or lesson_source.get("lesson_title") or fallback_lesson_name)
        .strip()
    )
    return lesson_name


def build_catalog_entry(chapter_name, lesson_name, lesson_source):
    content = extract_lesson_text(lesson_source, fallback_lesson_name=lesson_name)
    if not content:
        return None
    return {
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "content": content,
    }


def ensure_lesson_catalog(chapter_name, lesson_name, lesson_source, lesson_catalog):
    if isinstance(lesson_catalog, list) and lesson_catalog:
        entries = [entry for entry in lesson_catalog if isinstance(entry, dict)]
    else:
        entries = []

    current_key = normalize_lesson_key(lesson_name)
    if any(normalize_lesson_key(entry.get("lesson_name")) == current_key for entry in entries):
        return entries

    current_entry = build_catalog_entry(chapter_name, lesson_name, lesson_source)
    if current_entry:
        return [current_entry, *entries]
    return entries


def build_image_search_query(user_text, textbook_answer, extra_explanation, retrieval):
    parts = [str(user_text or "").strip(), str(textbook_answer or "").strip(), str(extra_explanation or "").strip()]
    for chunk in retrieval.get("chunks") or []:
        chunk_text = str(chunk.get("chunk_text") or "").strip()
        if chunk_text:
            parts.append(truncate_text(chunk_text, max_length=220))
        if len(parts) >= 5:
            break
    return "\n".join(part for part in parts if part).strip()


def select_images_for_reply(
    chapter_name,
    lesson_name,
    user_text,
    textbook_answer,
    extra_explanation,
    retrieval,
):
    query = build_image_search_query(user_text, textbook_answer, extra_explanation, retrieval)
    if not query:
        return []

    image = find_best_lesson_image(chapter_name, lesson_name, query)
    if image is None:
        return []
    return [image]


def select_images_for_concept(
    chapter_name,
    lesson_name,
    concept,
    response_text,
    used_image_ids=None,
):
    figure_hints = extract_figure_hints(concept.get("chunk_text"))
    for hint in figure_hints:
        image = find_best_lesson_image(
            chapter_name,
            lesson_name,
            hint,
            used_image_ids=used_image_ids,
        )
        if image is not None:
            return [image]

    query_parts = [
        strip_topic_numbering(concept.get("section_label") or ""),
        str(concept.get("chunk_text") or "").strip(),
        str(response_text or "").strip(),
    ]
    query = "\n".join(part for part in query_parts if part).strip()
    if not query:
        return []

    image = find_best_lesson_image(
        chapter_name,
        lesson_name,
        query,
        used_image_ids=used_image_ids,
    )
    if image is None:
        return []
    return [image]


def build_lesson_completion_payload(used_image_ids=None):
    response_text = (
        "দারুণ, এই lesson-এর মূল ধাপগুলো শেষ হয়েছে।\n\n"
        "চাইলে এখন আমি পুরো lesson-এর ছোট summary, revision, বা practice question দিতে পারি।"
    )
    return {
        "response": response_text,
        "images": [],
        "thread_state": {
            "mode": "lesson_flow",
            "concept_index": 0,
            "current_step_index": 0,
            "awaiting_understanding": False,
            "lesson_complete": True,
            "last_question": "",
            "used_image_ids": normalize_used_image_ids(used_image_ids),
        },
        "textbook_answer": response_text,
        "extra_explanation": "",
        "citations": [],
    }


def teach_lesson_concept(
    llm,
    chapter_name,
    lesson_name,
    concept,
    chat_model=None,
    re_explain=False,
    student_reply="",
    previous_question="",
    used_image_ids=None,
):
    messages = [
        SystemMessage(content=LESSON_FLOW_SYSTEM_PROMPT),
        HumanMessage(
            content=build_lesson_flow_prompt(
                chapter_name=chapter_name,
                lesson_name=lesson_name,
                concept=concept,
                student_reply=student_reply,
                previous_question=previous_question,
                re_explain=re_explain,
            )
        ),
    ]

    try:
        response = invoke_llm_with_logging(
            llm,
            messages,
            context="simple_graph.teach_lesson_concept",
            metadata={
                "chat_model": resolve_chat_model_id(chat_model),
                "chapter_name": chapter_name,
                "lesson_name": lesson_name,
                "concept_index": concept.get("concept_index"),
                "re_explain": re_explain,
            },
        )
    except Exception as exc:
        raise ValueError(normalize_error_message(exc)) from exc

    parsed = parse_teaching_response(response.content)
    response_markdown = compose_chat_markdown(
        parsed["textbook_answer"],
        parsed["extra_explanation"],
        [],
        check_question=parsed["check_question"],
    )
    selected_images = select_images_for_concept(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=concept,
        response_text=response_markdown,
        used_image_ids=used_image_ids,
    )
    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=selected_images,
        response_text=response_markdown,
        chat_model=chat_model,
    )
    updated_used_image_ids = merge_used_image_ids(
        used_image_ids,
        [image.get("image_id") for image in response_images],
    )

    return {
        "response": response_markdown,
        "images": response_images,
        "thread_state": {
            "mode": "lesson_flow",
            "concept_index": max(0, safe_int(concept.get("concept_index"), 0)),
            "current_step_index": max(0, safe_int(concept.get("concept_index"), 0)),
            "awaiting_understanding": True,
            "lesson_complete": False,
            "last_question": parsed["check_question"],
            "used_image_ids": updated_used_image_ids,
        },
        "textbook_answer": parsed["textbook_answer"],
        "extra_explanation": parsed["extra_explanation"],
        "check_question": parsed["check_question"],
        "citations": [],
    }


def run_lesson_flow_chat(
    thread_id,
    chapter_name,
    lesson_name,
    lesson_catalog,
    lesson_source,
    user_text,
    saved_thread_state=None,
    chat_model=None,
):
    del thread_id

    llm = get_llm(chat_model)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(chat_model))

    concepts = build_lesson_concepts(lesson_catalog, lesson_name, lesson_source=lesson_source)
    if not concepts:
        raise ValueError("Lesson content is empty")

    flow_state = normalize_lesson_flow_state(saved_thread_state)
    intro_request = is_introductory_question(user_text)
    if flow_state["mode"] != "lesson_flow" or (flow_state["lesson_complete"] and intro_request):
        flow_state = {
            "mode": "lesson_flow",
            "concept_index": 0,
            "current_step_index": 0,
            "awaiting_understanding": False,
            "lesson_complete": False,
            "last_question": "",
            "used_image_ids": [],
        }

    concept_index = min(flow_state["current_step_index"], len(concepts) - 1)
    current_concept = concepts[concept_index]

    if flow_state["awaiting_understanding"] and not flow_state["lesson_complete"]:
        understood = assess_understanding_reply(
            llm=llm,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            concept=current_concept,
            previous_question=flow_state["last_question"],
            student_reply=user_text,
        )
        if understood:
            next_index = concept_index + 1
            if next_index >= len(concepts):
                return build_lesson_completion_payload(flow_state["used_image_ids"])
            return teach_lesson_concept(
                llm=llm,
                chapter_name=chapter_name,
                lesson_name=lesson_name,
                concept=concepts[next_index],
                chat_model=chat_model,
                used_image_ids=flow_state["used_image_ids"],
            )

        return teach_lesson_concept(
            llm=llm,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            concept=current_concept,
            chat_model=chat_model,
            re_explain=True,
            student_reply=user_text,
            previous_question=flow_state["last_question"],
            used_image_ids=flow_state["used_image_ids"],
        )

    return teach_lesson_concept(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=current_concept,
        chat_model=chat_model,
        used_image_ids=flow_state["used_image_ids"],
    )


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
    messages.extend(build_history_messages(history))
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
    response_markdown = compose_chat_markdown(
        parsed["textbook_answer"],
        parsed["extra_explanation"],
        citations,
    )

    image_lesson_name = str(retrieval.get("source_lesson_name") or lesson_name).strip() or lesson_name
    selected_images = select_images_for_reply(
        chapter_name=chapter_name,
        lesson_name=image_lesson_name,
        user_text=user_text,
        textbook_answer=parsed["textbook_answer"],
        extra_explanation=parsed["extra_explanation"],
        retrieval=retrieval,
    )
    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=image_lesson_name,
        selected_images=selected_images,
        response_text=response_markdown,
        chat_model=chat_model,
    )

    return {
        "response": response_markdown,
        "images": response_images,
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
        lesson_catalog = lesson_source
        lesson_source = None

    catalog = ensure_lesson_catalog(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_source=lesson_source,
        lesson_catalog=lesson_catalog,
    )
    if not catalog:
        raise ValueError("Lesson content is empty")

    flow_state = normalize_lesson_flow_state(saved_thread_state)
    if (flow_state["mode"] == "lesson_flow" and not flow_state["lesson_complete"]) or (
        flow_state["lesson_complete"] and is_introductory_question(user_text)
    ) or (
        flow_state["mode"] != "lesson_flow" and is_introductory_question(user_text)
    ):
        return run_lesson_flow_chat(
            thread_id=thread_id,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            lesson_catalog=catalog,
            lesson_source=lesson_source,
            user_text=user_text,
            saved_thread_state=saved_thread_state,
            chat_model=chat_model,
        )

    return run_grounded_chat(
        thread_id=thread_id,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        lesson_catalog=catalog,
        history=history,
        user_text=user_text,
        chat_model=chat_model,
    )
