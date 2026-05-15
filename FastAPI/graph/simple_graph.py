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
    normalize_lesson_key,
    truncate_text,
)
from graph.llm_logging import invoke_llm_with_logging


GROUNDING_SYSTEM_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "You must respond in valid JSON only, with no markdown fences.\n"
    "Return this exact schema:\n"
    "{\n"
    '  "textbook_answer": "direct study answer",\n'
    '  "extra_explanation": "optional extra explanation"\n'
    "}\n"
    "Rules:\n"
    "- Answer the student's study question naturally using the conversation context and your physics knowledge.\n"
    "- Do not pretend the answer is unavailable just because it is not exactly from the current lesson.\n"
    "- If the question is related to study, physics, math, exams, or the current chapter, answer it directly first.\n"
    "- Use the current chapter and lesson only as soft context; do not force the answer to stay inside that lesson.\n"
    "- If the question is unrelated to study, reply briefly and steer back to study.\n"
    "- Write clean, readable paragraphs and markdown lists. Do not include the literal characters \\n in normal prose.\n"
    "- When you write formulas or symbols, always use Markdown math delimiters: inline $...$ and block $$...$$.\n"
    "- Because the response is JSON, escape every backslash inside LaTeX so JSON stays valid.\n"
    "- For multiplied units or symbols, use LaTeX operators like \\cdot and \\times inside math, not Unicode characters like · or ×.\n"
    "- When writing units such as newton-meter, prefer $N \\cdot m$ instead of text like N·m inside math.\n"
    "- Do not write raw LaTeX commands like \\frac outside math delimiters.\n"
    "- Keep Bangla words outside the math delimiters whenever possible.\n"
    "- When listing formulas, prefer short markdown bullets and wrap each formula in $...$ or $$...$$.\n"
    "- Never mention any diagram/figure serial number like চিত্র 2.6 or Figure 3.1.\n"
    "- Do not ask the student to look at a figure unless an image is rendered in chat.\n"
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
    '  "check_question": "one short check question or simple practice problem"\n'
    "}\n"
    "Rules:\n"
    "- Read the FULL topic content carefully before replying.\n"
    "- Use only the provided concept text.\n"
    "- Teach only this one topic. Do not jump to the next topic.\n"
    "- Keep each teaching turn compact: usually 120-180 words, unless a short derivation needs slightly more.\n"
    "- Explain the topic enough to teach it, but do not dump the whole lesson in one turn.\n"
    "- Cover all important ideas present in the topic content. Do not skip key points.\n"
    "- Teach naturally like a real tutor: use a short example, ask the student to notice patterns, and keep the lesson moving.\n"
    "- Do not dump a dry list of mini-topics.\n"
    "- If re-explaining, point out the exact misconception first, then use a different example or angle.\n"
    "- Use markdown structure, not plain text only.\n"
    "- Start textbook_answer with a short markdown heading for the current topic.\n"
    "- Use short bullets where they help clarity.\n"
    "- If the topic content contains a notation, equation, symbol, definition, or named rule, include it clearly.\n"
    "- If the topic includes a derivation or proof idea, explain that proof path clearly in simple steps.\n"
    "- Use simple Bangla-friendly language.\n"
    "- Use simplified examples or analogies when they help understanding.\n"
    "- Do not mention topic or lesson serial numbers like 2.6, 3.2, etc. Start directly with the idea.\n"
    "- End each turn with exactly one short check to verify understanding of this topic.\n"
    "- The check_question value must not include prefixes like 'ছোট প্রশ্ন:' or 'Question:'.\n"
    "- Do not ask two checks at once. For example, do not ask positive-charge and negative-charge direction in the same check.\n"
    "- If the topic is mathematical, use a very simple unsolved numeric practice problem instead of only a theory question.\n"
    "- If you give a practice problem, do not solve it in the same turn.\n"
    "- Do not repeat the same type of check unless the student made a conceptual mistake.\n"
    "- For electric potential direction questions, keep this rule consistent: positive charge moves from higher potential to lower potential, and negative charge moves the opposite way.\n"
    "- Bold the asked question\n"
    "- Do not say the request is unclear.\n"
    "- Never mention any figure or diagram serial number such as চিত্র 2.6 or Figure 3.1.\n"
    "- Explain figure-related ideas in plain words; do not ask the student to look at a figure here.\n"
    "- When writing formulas or symbols, always use Markdown math delimiters: inline $...$ and block $$...$$.\n"
    "- Write units in plain text when possible, for example kg m^2 s^-1. Do not use LaTeX spacing commands like \\!, \\quad, or \\qquad.\n"
)
LESSON_FLOW_JSON_RETRY_SYSTEM_PROMPT = (
    "You are repairing a tutor response for a Bangladeshi HSC physics app.\n"
    "Return valid JSON only, with no markdown fences and no commentary.\n"
    "Use exactly this schema:\n"
    "{\n"
    '  "textbook_answer": "compact markdown teaching explanation",\n'
    '  "extra_explanation": "optional short intuition or empty string",\n'
    '  "check_question": "one short check question or unsolved practice problem"\n'
    "}\n"
    "Strict rules:\n"
    "- Regenerate from scratch. Do not copy the invalid previous response.\n"
    "- Keep the whole JSON response under 1200 characters.\n"
    "- Use at most one displayed equation.\n"
    "- Escape JSON strings correctly.\n"
    "- Do not use LaTeX spacing commands such as \\!, \\quad, or \\qquad.\n"
    "- Write units in plain text like kg m^2 s^-1 when possible.\n"
    "- check_question must contain only one focused question or one unsolved practice problem."
)
LESSON_FLOW_QUESTION_SYSTEM_PROMPT = (
    "You are a Bangladeshi HSC physics tutor handling a student's follow-up question while a lesson topic is in progress.\n"
    "You must respond in valid JSON only, with no markdown fences.\n"
    "Return this exact schema:\n"
    "{\n"
    '  "textbook_answer": "direct answer in tutor style, tied back to the current lesson topic",\n'
    '  "extra_explanation": "optional broader physics explanation",\n'
    '  "check_question": "one short check question or simple practice problem about the current lesson topic"\n'
    "}\n"
    "Rules:\n"
    "- Answer the student's question first, clearly and naturally.\n"
    "- If the student asks for an example, analogy, or math problem, provide that first.\n"
    "- If the student asks for a practice/math problem, give one short unsolved problem and at most one small hint. Do not include the final answer or solution steps.\n"
    "- After answering, return to the pending lesson check instead of moving ahead.\n"
    "- Keep the lesson flow anchored to the current topic; do not jump ahead to the next topic.\n"
    "- If the exact answer is outside the current topic text or outside this lesson but still physics-related, answer it properly in extra_explanation and reconnect to the current topic.\n"
    "- If the question is non-physics, reply briefly and politely, then return to the current topic flow.\n"
    "- Use simple, student-friendly language and include equations/notation/proof steps when needed.\n"
    "- check_question must be exactly one short check for the current topic, with no prefix like 'ছোট প্রশ্ন:' or 'Question:'.\n"
    "- Do not ask two checks at once.\n"
    "- For electric potential direction questions, keep this rule consistent: positive charge moves from higher potential to lower potential, and negative charge moves the opposite way.\n"
    "- Never mention any figure or diagram serial number such as চিত্র 2.6 or Figure 3.1.\n"
    "- Do not say the request is unclear."
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
MAX_LESSON_FLOW_CONCEPTS = 8
IMAGE_REUSE_SCORE_THRESHOLD = 8
VISUAL_IMAGE_KEYWORDS = {
    "চিত্র",
    "ছবি",
    "রেখাচিত্র",
    "গ্রাফ",
    "ডায়াগ্রাম",
    "ডায়াগ্রাম",
    "বলরেখা",
    "সার্কিট",
    "লেন্স",
    "রশ্মি",
    "তরঙ্গ",
    "image",
    "picture",
    "diagram",
    "figure",
    "graph",
    "draw",
    "sketch",
    "circuit",
    "lens",
    "ray",
    "wave",
    "field line",
    "free body",
    "vector",
}
MATH_CONCEPT_KEYWORDS = {
    "সূত্র",
    "সমীকরণ",
    "গাণিতিক",
    "মান নির্ণ",
    "হিসাব",
    "প্রমাণ",
    "derive",
    "derivation",
    "formula",
    "equation",
    "calculate",
    "solve",
}
PRACTICE_REQUEST_KEYWORDS = {
    "math",
    "problem",
    "practice",
    "example",
    "exercise",
    "numerical",
    "solve",
    "অংক",
    "গণিত",
    "সমস্যা",
    "উদাহরণ",
    "অনুশীলন",
}
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
LITERAL_ESCAPED_ANSWER_MARKER_PATTERN = re.compile(
    r"\\\\+\s*(?=(?:উত্তর|সমাধান|Answer|Solution|Ans)\b)",
    flags=re.IGNORECASE,
)
CHECK_QUESTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:[*_`#\s]*)(?:(?:ছোট|চেক)\s*)?(?:প্রশ্ন|question|check)\s*[:：\-]\s*",
    flags=re.IGNORECASE,
)
PRACTICE_ANSWER_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[*_`#\s]*)(?:উত্তর|সমাধান|answer|solution|ans)\s*[:：\-]",
    flags=re.IGNORECASE,
)
POTENTIAL_VALUE_PATTERN = re.compile(r"([+\-]?\d+(?:\.\d+)?)\s*v\b", flags=re.IGNORECASE)
BANGLA_DIGIT_TRANSLATION = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
TOPIC_NUMBER_PREFIX_PATTERN = re.compile(r"^\s*[০-৯0-9]+(?:\s*[.\-:]\s*[০-৯0-9]+)*\s*[:।.-]?\s*")
FIGURE_TITLE_PATTERN = re.compile(r"চিত্র(?:\s*[০-৯0-9]+(?:\.[০-৯0-9]+)*)?\s*[:：-]\s*([^\n\r]+)")
FIGURE_LINE_PATTERN = re.compile(r"([^\n\r]*চিত্র[^\n\r]*)")
BANGLA_DIAGRAM_SERIAL_PATTERN = re.compile(
    r"চিত্র\s*[০-৯0-9]+(?:\s*[.\-]\s*[০-৯0-9]+)*\s*[:：-]?\s*",
    flags=re.IGNORECASE,
)
ENGLISH_DIAGRAM_SERIAL_PATTERN = re.compile(
    r"\b(?:figure|fig\.?|diagram)\s*[0-9]+(?:\s*[.\-]\s*[0-9]+)*\s*[:：-]?\s*",
    flags=re.IGNORECASE,
)
IMAGE_REFERENCE_LINE_PATTERN = re.compile(r"(?im)^\s*(?:[-*]\s*)?(?:চিত্র|figure|fig\.?|diagram|ছবি|image)\b[^\n]*$")
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
LESSON_START_PHRASES = {
    "start",
    "begin",
    "continue",
    "teach",
    "learn",
    "lesson",
    "from beginning",
    "from scratch",
    "start learning",
    "শুরু",
    "শুরু করি",
    "শুরু করো",
    "শিখতে চাই",
    "শেখাও",
    "পড়াও",
    "পড়াও",
    "বুঝাও",
    "বুঝিয়ে দাও",
    "বুঝিয়ে দাও",
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

    if provider == "groq" and model:
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
    return "GROQ_API_KEY is not set"


def get_llm(selected_model=None):
    model_config = resolve_chat_model_config(selected_model)

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


def text_contains_any(value, phrases):
    text = normalize_text(value)
    return any(phrase in text for phrase in phrases)


def needs_visual_image(*values):
    return text_contains_any("\n".join(str(value or "") for value in values), VISUAL_IMAGE_KEYWORDS)


def is_math_concept(concept):
    text = f"{concept.get('section_label') or ''}\n{concept.get('chunk_text') or ''}"
    return bool(re.search(r"[$=]|\\(?:frac|sqrt|sum|int)\b", text)) or text_contains_any(text, MATH_CONCEPT_KEYWORDS)


def is_practice_request(value):
    return text_contains_any(value, PRACTICE_REQUEST_KEYWORDS)


def normalize_grounded_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = (
        text.replace("\\\\(", "$")
        .replace("\\\\)", "$")
        .replace("\\(", "$")
        .replace("\\)", "$")
        .replace("\\\\,", " ")
        .replace("\\,", " ")
        .replace("へ", " দিকে")
    )
    text = LITERAL_NEWLINE_PATTERN.sub("\n", text)
    text = LITERAL_TAB_PATTERN.sub(" ", text)
    text = LITERAL_ESCAPED_ANSWER_MARKER_PATTERN.sub("\n", text)
    text = fix_potential_direction_text(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fix_potential_direction_text(value):
    text = str(value or "")
    fixes = [
        (
            "নিম্ন বিভবের দিকে ঋণাত্মক আধান",
            "ঋণাত্মক আধান নিম্ন বিভব থেকে উচ্চ বিভবের দিকে",
        ),
        (
            "কম বিভবের দিকে ঋণাত্মক আধান",
            "ঋণাত্মক আধান কম বিভব থেকে বেশি বিভবের দিকে",
        ),
        (
            "negative charge moves from higher potential to lower potential",
            "negative charge moves from lower potential to higher potential",
        ),
        (
            "electrons move from higher potential to lower potential",
            "electrons move from lower potential to higher potential",
        ),
    ]
    for wrong, right in fixes:
        text = re.sub(re.escape(wrong), right, text, flags=re.IGNORECASE)

    contradiction_patterns = [
        (
            r"বেশি আধানযুক্ত\s*\(কিন্তু কম বিভবযুক্ত\)\s*বস্তু থেকে কম আধানযুক্ত\s*\(কিন্তু বেশি বিভবযুক্ত\)\s*বস্তুতে আধান প্রবাহিত হয়",
            "আধানের পরিমাণ নয়, বিভবের পার্থক্যই প্রবাহের দিক ঠিক করে; ধনাত্মক আধান উচ্চ বিভব থেকে নিম্ন বিভবের দিকে প্রবাহিত হয়",
        ),
        (
            r"আধান কেবল এক বস্তু থেকে অন্য বস্তুর দিকে স্থানান্তরিত হতে পারে। এই ধারণা তড়িৎ বিভবের সঙ্গে ঘনিষ্ঠভাবে যুক্ত, কারণ বিভব হল আধানের ‘শক্তি স্তর’ যা আধানের প্রবাহকে চালিত করে।",
            "আধান এক বস্তু থেকে অন্য বস্তুর দিকে স্থানান্তরিত হতে পারে। এই ধারণা তড়িৎ বিভবের সঙ্গে যুক্ত, কারণ বিভবের পার্থক্যই আধান প্রবাহের চালিকা শক্তি।",
        ),
        (
            r"তাই উচ্চ বিভবের দিকে আধানের প্রবাহ হবে",
            "তাই ধনাত্মক আধান উচ্চ বিভব থেকে নিম্ন বিভবের দিকে প্রবাহিত হবে",
        ),
        (
            r"charge flows toward higher potential",
            "positive charge flows from higher potential to lower potential",
        ),
    ]
    for pattern, replacement in contradiction_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def normalize_check_question(value):
    text = normalize_grounded_text(value)
    text = re.sub(r"^\s*[-*]\s*", "", text).strip()
    text = CHECK_QUESTION_PREFIX_PATTERN.sub("", text).strip()
    text = re.sub(r"^\*\*(.*?)\*\*$", r"\1", text).strip()
    text = text.strip("*_` ").strip()
    return text


def remove_practice_answer_sections(value):
    text = normalize_grounded_text(value)
    marker = PRACTICE_ANSWER_SECTION_PATTERN.search(text)
    if marker:
        text = text[: marker.start()].strip()
    return text


def build_practice_request_intro(concept):
    concept_text = normalize_text(f"{concept.get('section_label') or ''}\n{concept.get('chunk_text') or ''}")
    if "বিভব" in concept_text or "potential" in concept_text:
        return (
            "চলো একটি ছোট অনুশীলন করি। আগে নিজে চেষ্টা করো, তারপর তোমার উত্তর দেখে এগোব।",
            "ইঙ্গিত: আগে কোন বিভবটি বেশি, সেটি চিহ্নিত করো; আধানের ধরনটাও খেয়াল করো।",
        )
    return (
        "চলো একটি ছোট অনুশীলন করি। আগে নিজে চেষ্টা করো, তারপর তোমার উত্তর দেখে এগোব।",
        "ইঙ্গিত: প্রশ্নে দেওয়া মান বা শর্ত থেকে কোন নিয়মটি লাগবে, সেটি আগে ধরো।",
    )


def check_question_type(question):
    text = normalize_text(question)
    if not text:
        return ""
    if any(token in text for token in ("কোন দিক", "দিকে", "প্রবাহিত হবে", "কোন ধরণের", "কোন ধরনের", "from", "to")) and any(
        token in text for token in ("বিভব", "উচ্চ", "নিম্ন", "potential", "v")
    ):
        return "direction"
    if any(token in text for token in ("নির্ভর", "চালক", "কারণে", "কিসের উপর", "depends", "driver")):
        return "driver"
    if any(token in text for token in ("থাম", "বন্ধ", "সমান", "stop", "equal")):
        return "stop"
    if any(token in text for token in ("তাপ", "তাপমাত্রা", "পানি", "তরল", "মুক্ততল", "analogy")):
        return "analogy"
    if any(token in text for token in ("সংজ্ঞা", "কী বোঝ", "কি বোঝ", "definition", "unit", "একক")):
        return "definition"
    return ""


def check_question_candidates(concept):
    concept_text = normalize_text(f"{concept.get('section_label') or ''}\n{concept.get('chunk_text') or ''}")
    if "বিভব" in concept_text or "potential" in concept_text:
        return [
            ("driver", "আধান প্রবাহের দিক ঠিক করতে মোট আধান বেশি গুরুত্বপূর্ণ, নাকি বিভবের পার্থক্য?"),
            ("stop", "দুই পরিবাহীর বিভব সমান হয়ে গেলে আধান প্রবাহ কেন থেমে যায়?"),
            ("analogy", "তাপমাত্রা-তাপ প্রবাহের সঙ্গে বিভব-আধান প্রবাহের মিলটা এক বাক্যে বলো।"),
            ("definition", "তড়িৎ বিভব বলতে এক কথায় কী বোঝায়?"),
        ]
    return [
        ("driver", "এই অংশে পরিবর্তন বা প্রবাহ ঘটার মূল কারণটি কী?"),
        ("definition", "এই ধারণাটিকে এক বাক্যে কীভাবে বলবে?"),
    ]


def avoid_repeated_check_question(check_question, concept, previous_question, allow_repeat=False):
    cleaned_question = normalize_check_question(check_question)
    if allow_repeat or not previous_question:
        return cleaned_question

    previous_type = check_question_type(previous_question)
    current_type = check_question_type(cleaned_question)
    if not previous_type or current_type != previous_type:
        return cleaned_question

    for candidate_type, candidate in check_question_candidates(concept):
        if candidate_type != previous_type:
            return candidate
    return cleaned_question


def strip_diagram_serial_numbers(value):
    text = str(value or "")
    text = BANGLA_DIAGRAM_SERIAL_PATTERN.sub("চিত্র ", text)
    text = ENGLISH_DIAGRAM_SERIAL_PATTERN.sub("figure ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def remove_unrendered_image_references(value):
    text = str(value or "")
    text = IMAGE_REFERENCE_LINE_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def prepend_lesson_feedback(response_text, feedback_text):
    body = normalize_grounded_text(response_text)
    feedback = normalize_grounded_text(feedback_text)
    if not feedback:
        return body
    if not body:
        return feedback
    return f"{feedback}\n\n{body}"


def apply_image_reference_policy(response_text, response_images):
    cleaned = normalize_grounded_text(response_text)
    if response_images:
        return cleaned
    return remove_unrendered_image_references(cleaned)


def collapse_inline_whitespace(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def strip_topic_numbering(value):
    text = collapse_inline_whitespace(value)
    stripped = TOPIC_NUMBER_PREFIX_PATTERN.sub("", text).strip()
    return stripped or text


def derive_topic_title_from_text(value, fallback_index):
    text = normalize_grounded_text(value)
    text = re.sub(r"^#+\s*", "", text).strip()
    lines = [collapse_inline_whitespace(line) for line in text.splitlines() if collapse_inline_whitespace(line)]
    candidates = []
    if lines:
        candidates.append(lines[0])

    fragments = re.split(r"(?<=[।.!?])\s+", collapse_inline_whitespace(text))
    candidates.extend(fragment for fragment in fragments if fragment)

    for candidate in candidates:
        cleaned = strip_topic_numbering(strip_diagram_serial_numbers(candidate))
        cleaned = re.sub(r"[*_`]+", "", cleaned).strip(" -:।.")
        if not cleaned:
            continue
        words = cleaned.split()
        if len(words) > 8:
            cleaned = " ".join(words[:8]).strip(" -:।.")
        if len(cleaned) > 80:
            cleaned = cleaned[:77].rstrip(" ,;:-।.") + "..."
        if cleaned and not is_generic_chunk_label(cleaned):
            return cleaned

    return f"ধারণা {fallback_index}"


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


def compose_chat_markdown(textbook_answer, extra_explanation, citations, check_question="", next_step_hint=""):
    textbook_answer = strip_diagram_serial_numbers(normalize_grounded_text(textbook_answer))
    extra_explanation = strip_diagram_serial_numbers(normalize_grounded_text(extra_explanation))
    check_question = strip_diagram_serial_numbers(normalize_check_question(check_question))
    next_step_hint = strip_diagram_serial_numbers(normalize_grounded_text(next_step_hint))
    del citations

    parts = []
    if textbook_answer:
        parts.append(textbook_answer)
    if extra_explanation:
        parts.append(extra_explanation)
    if next_step_hint:
        parts.append(next_step_hint)
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
    next_hint = str(item.get("next_hint") or "").strip()
    return compose_chat_markdown(
        textbook_answer,
        extra_explanation,
        citations,
        check_question=check_question,
        next_step_hint=next_hint,
    )


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


def build_study_chat_prompt(chapter_name, lesson_name, user_text):
    return (
        f"Current study context:\n"
        f"- Chapter: {chapter_name}\n"
        f"- Lesson: {lesson_name}\n\n"
        "Answer the student's message naturally. Use the chapter/lesson only as helpful context, "
        "not as a hard boundary.\n\n"
        f"Student message:\n{user_text}"
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
    check_question = normalize_check_question(payload.get("check_question") or payload.get("question") or "")

    if not textbook_answer:
        raise ValueError("The lesson flow payload must contain a textbook_answer.")
    if not check_question:
        raise ValueError("The lesson flow payload must contain a check_question.")

    return {
        "textbook_answer": textbook_answer,
        "extra_explanation": extra_explanation,
        "check_question": check_question,
    }


def invoke_teaching_llm_for_json(llm, messages, context, metadata=None, retry_user_prompt=""):
    response = invoke_llm_with_logging(
        llm,
        messages,
        context=context,
        metadata=metadata,
    )

    try:
        return parse_teaching_response(response.content)
    except ValueError as exc:
        repair_prompt = (
            "The previous response was invalid JSON and could not be used.\n"
            f"Parser error: {exc}\n\n"
            "Regenerate the answer from scratch for this original task:\n\n"
            f"{retry_user_prompt}"
        )
        retry_response = invoke_llm_with_logging(
            llm,
            [
                SystemMessage(content=LESSON_FLOW_JSON_RETRY_SYSTEM_PROMPT),
                HumanMessage(content=repair_prompt),
            ],
            context=f"{context}.retry_json",
            metadata={
                **(metadata or {}),
                "retry_reason": str(exc)[:200],
            },
        )
        return parse_teaching_response(retry_response.content)


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
    return strip_diagram_serial_numbers(strip_topic_numbering(text))


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


def is_generic_chunk_label(value):
    return bool(re.match(r"(?i)^(?:page\s+\d+|chunk\s+\d+|ধারণা\s+\d+)(?:\s*/.*)?$", str(value or "").strip()))


def compact_group_label(labels, group_index):
    cleaned = [strip_topic_numbering(label) for label in labels if str(label or "").strip()]
    meaningful = [label for label in cleaned if label and not is_generic_chunk_label(label)]
    if meaningful:
        return meaningful[0]
    return f"ধারণা {group_index}"


def compact_lesson_flow_chunks(chunks, max_concepts=MAX_LESSON_FLOW_CONCEPTS):
    valid_chunks = [
        chunk for chunk in chunks
        if isinstance(chunk, dict) and str(chunk.get("chunk_text") or "").strip()
    ]
    if len(valid_chunks) <= max_concepts:
        return valid_chunks

    groups = []
    group_size = max(1, (len(valid_chunks) + max_concepts - 1) // max_concepts)
    for start in range(0, len(valid_chunks), group_size):
        current = valid_chunks[start:start + group_size]
        labels = [item.get("section_label") for item in current]
        groups.append(
            {
                "section_label": compact_group_label(labels, len(groups) + 1),
                "chunk_text": "\n\n".join(str(item.get("chunk_text") or "").strip() for item in current).strip(),
            }
        )

    return groups


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
    raw_chunks = compact_lesson_flow_chunks(chunk_lesson_content(lesson_entry.get("content")))
    for index, chunk in enumerate(raw_chunks, start=1):
        chunk_text = str(chunk.get("chunk_text") or "").strip()
        if not chunk_text:
            continue
        raw_label = strip_topic_numbering(chunk.get("section_label") or "")
        section_label = (
            derive_topic_title_from_text(chunk_text, index)
            if not raw_label or is_generic_chunk_label(raw_label)
            else raw_label
        )
        concepts.append(
            {
                "concept_index": len(concepts),
                "display_index": index,
                "section_label": section_label,
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
    check_instruction = (
        "End with one very simple unsolved numeric practice problem from this topic. Do not include its answer."
        if is_math_concept(concept)
        else "End with one short conceptual check question for this topic."
    )
    action_line = (
        "The student did not clearly show understanding yet. Re-explain the same topic more simply and more clearly, then give one focused check."
        if re_explain
        else "Teach this topic clearly in natural tutor style, then give one focused check."
    )
    follow_up_block = ""
    if previous_question:
        follow_up_block = (
            f"Previous check question:\n{previous_question}\n\n"
        )
    if re_explain:
        follow_up_block += f"Student reply:\n{student_reply}\n\n"

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
        "Give a solid but compact teaching explanation for this topic in this turn.\n"
        "Use at most two short paragraphs plus a few bullets only when they help.\n"
        "Explain the important parts of this topic clearly, but do not move to the next topic.\n"
        "Do not dump a plain list of all lesson topics; keep it conversational and concept-focused.\n"
        "Use markdown headings and, when helpful, short bullets.\n"
        "If the topic includes equation, display it in a clear and readable format.\n"
        "If the topic includes notation, symbols, equations, definitions, or proof steps, include them clearly.\n"
        f"{check_instruction}\n"
        "The check_question field must contain only the check itself, without 'ছোট প্রশ্ন:' or similar prefixes.\n"
        "Make the check one focused task only.\n"
        "Avoid the same style as the previous check unless the student made a conceptual mistake.\n"
        "Do not repeat any lesson number or serial number such as 2.6 or 3.2.\n"
        "If a figure is mentioned in the source text, explain its idea in words only and do not mention any figure serial.\n\n"
        f"{follow_up_block}"
        f"{figure_block}"
        f"Full topic content:\n{concept.get('chunk_text')}"
    )


def build_lesson_flow_question_prompt(
    chapter_name,
    lesson_name,
    concept,
    student_question,
    previous_question="",
):
    if is_practice_request(student_question):
        check_instruction = (
            "The student is asking for practice. Give exactly one short unsolved practice problem tied to this topic. "
            "You may add one short hint, but do not include the final answer, solution steps, or any line starting with উত্তর, Answer, or Solution. "
            "Set check_question to exactly that same unsolved problem."
        )
    elif previous_question:
        check_instruction = "After answering, repeat the previous check exactly so the student can answer it."
    else:
        check_instruction = (
            "After answering, give one very simple numeric practice problem from this topic."
            if is_math_concept(concept)
            else "After answering, give one short conceptual check question for this topic."
        )
    previous_block = ""
    if previous_question:
        previous_block = f"Previous check question:\n{previous_question}\n\n"

    return (
        f"Chapter: {chapter_name}\n"
        f"Lesson: {lesson_name}\n"
        f"Current topic: {strip_topic_numbering(concept.get('section_label'))}\n\n"
        "The lesson is in progress and the student asked a follow-up question.\n"
        "Answer the question clearly first, then reconnect to this current topic.\n"
        "If the question is outside this lesson but physics-related, still answer it properly and then return to this topic flow.\n"
        "Do not move to the next topic yet.\n"
        f"{check_instruction}\n"
        "Keep the reply compact and conversational.\n\n"
        f"{previous_block}"
        f"Current topic content:\n{concept.get('chunk_text')}\n\n"
        f"Student question:\n{student_question}"
    )


def normalize_joined_text(value):
    return re.sub(r"\s+", "", normalize_text(value))


def contains_understanding_phrase(normalized_text, phrase):
    phrase = normalize_text(phrase)
    if not phrase:
        return False
    if re.fullmatch(r"[a-z0-9\u0980-\u09ff]+", phrase):
        tokens = set(re.findall(r"[a-z0-9]+|[\u0980-\u09ff]+", normalized_text))
        return phrase in tokens
    return phrase in normalized_text


def normalize_direction_text(value):
    return normalize_joined_text(value).replace("_", "").replace("−", "-").replace("–", "-").replace("—", "-")


def question_asks_negative_charge(question):
    text = normalize_text(question)
    asks_negative = any(token in text for token in ("ঋণাত্মক", "negative", "electron", "ইলেকট্রন"))
    asks_positive = any(token in text for token in ("ধনাত্মক", "positive"))
    return asks_negative and not asks_positive


def normalize_potential_value_label(raw_number):
    value_text = str(raw_number or "").strip()
    if value_text.startswith("+"):
        return f"+{value_text[1:]}v"
    return f"{value_text}v"


def potential_numeric_pair(question):
    normalized = (
        str(question or "")
        .translate(BANGLA_DIGIT_TRANSLATION)
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
    )
    values = []
    seen_labels = set()
    for match in POTENTIAL_VALUE_PATTERN.finditer(normalized):
        raw_number = match.group(1)
        label = normalize_potential_value_label(raw_number)
        if label in seen_labels:
            continue
        seen_labels.add(label)
        try:
            numeric_value = float(raw_number)
        except ValueError:
            continue
        values.append((numeric_value, label))

    if len(values) < 2:
        return None

    high_value, high_label = max(values, key=lambda item: item[0])
    low_value, low_label = min(values, key=lambda item: item[0])
    if high_value == low_value:
        return None
    return high_label, low_label


def build_next_step_hint(concepts, concept_index):
    del concepts, concept_index
    return ""


def is_student_question_in_lesson_flow(user_text):
    text = str(user_text or "").strip()
    if not text:
        return False

    normalized = normalize_text(text)
    joined = normalize_joined_text(text)
    positive_joined = {normalize_joined_text(item) for item in POSITIVE_UNDERSTANDING_PHRASES}
    negative_joined = {normalize_joined_text(item) for item in NEGATIVE_UNDERSTANDING_PHRASES}

    if normalized in POSITIVE_UNDERSTANDING_PHRASES or joined in positive_joined:
        return False
    if normalized in NEGATIVE_UNDERSTANDING_PHRASES or joined in negative_joined:
        return False

    tokens = tokenize(text)
    if not tokens:
        return False

    if "?" in text or "？" in text:
        return True

    question_tokens = {
        "why",
        "how",
        "what",
          "which",
          "when",
          "where",
          "give",
          "show",
          "problem",
          "practice",
          "example",
          "exercise",
          "math",
          "numerical",
          "explain",
          "derive",
          "proof",
        "difference",
        "কেন",
        "কিভাবে",
        "কীভাবে",
        "কী",
        "কি",
        "কখন",
        "কোথায়",
          "কোথায়",
          "দাও",
          "দিন",
          "দেখাও",
          "বোঝাও",
          "উদাহরণ",
          "সমস্যা",
          "অনুশীলন",
          "অংক",
          "গণিত",
          "ব্যাখ্যা",
          "প্রমাণ",
          "চিত্র",
          "ছবি",
          "রেখাচিত্র",
          "ডায়াগ্রাম",
          "ডায়াগ্রাম",
          "diagram",
          "image",
          "picture",
          "graph",
      }
    if tokens & question_tokens:
        return True

    return False


def is_lesson_start_request(user_text):
    text = str(user_text or "").strip()
    if not text:
        return True

    if is_introductory_question(text):
        return True

    normalized = normalize_text(text)
    joined = normalize_joined_text(text)
    if normalized in LESSON_START_PHRASES:
        return True

    if any(phrase in normalized for phrase in LESSON_START_PHRASES if " " in phrase):
        return True

    tokens = tokenize(text)
    if tokens & LESSON_START_PHRASES:
        return True

    bangla_starts = ("শুরু", "শিখ", "শেখ", "পড়া", "পড়া", "পড়াও", "পড়াও", "বুঝ")
    if any(marker in joined for marker in bangla_starts):
        return True

    return False


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
        if contains_understanding_phrase(normalized, phrase):
            return True
    for phrase in NEGATIVE_UNDERSTANDING_PHRASES:
        if contains_understanding_phrase(normalized, phrase):
            return False
    return None


def short_non_negative_reply(user_text):
    normalized = normalize_text(user_text)
    if not normalized:
        return False
    if any(contains_understanding_phrase(normalized, phrase) for phrase in NEGATIVE_UNDERSTANDING_PHRASES):
        return False
    if "?" in user_text:
        return False
    token_count = len(re.findall(r"[a-z0-9\u0980-\u09ff]+", normalized))
    return 0 < token_count <= 4


def potential_direction_pair(question):
    numeric_pair = potential_numeric_pair(question)
    if numeric_pair is not None:
        return numeric_pair

    text = normalize_direction_text(question)
    comparisons = [
        ("v1>v2", "v1", "v2"),
        ("v2<v1", "v1", "v2"),
        ("v1<v2", "v2", "v1"),
        ("v2>v1", "v2", "v1"),
        ("va>vb", "a", "b"),
        ("vb<va", "a", "b"),
        ("va<vb", "b", "a"),
        ("vb>va", "b", "a"),
    ]
    for marker, high_label, low_label in comparisons:
        if marker in text:
            return high_label, low_label

    first_low = re.search(r"প্রথম[^।,.]*বিভব[^।,.]*কম", text)
    first_high = re.search(r"প্রথম[^।,.]*বিভব[^।,.]*বেশি", text)
    other_high = re.search(r"(?:দ্বিতীয়|দ্বিতীয়|অন্য)[^।,.]*বিভব[^।,.]*বেশি", text)
    other_low = re.search(r"(?:দ্বিতীয়|দ্বিতীয়|অন্য)[^।,.]*বিভব[^।,.]*কম", text)
    if first_low and other_high:
        return "v2", "v1"
    if first_high and other_low:
        return "v1", "v2"
    return None


def potential_label_aliases(label):
    aliases = {
        "v1": {"v1", "1", "প্রথম", "first"},
        "v2": {"v2", "2", "দ্বিতীয়", "দ্বিতীয়", "second"},
        "a": {"a", "va"},
        "b": {"b", "vb"},
    }
    if label in aliases:
        return aliases[label]

    value_match = re.fullmatch(r"([+\-]?\d+(?:\.\d+)?)v", str(label or ""))
    if value_match:
        raw_number = value_match.group(1)
        normalized_label = normalize_potential_value_label(raw_number)
        plain_number = raw_number[1:] if raw_number.startswith("+") else raw_number
        sign_variant = normalized_label.replace("-", "−")
        return {normalized_label, sign_variant, f"{plain_number}v", plain_number}

    return {label}


def reply_has_direction(reply, source_label, target_label):
    text = normalize_direction_text(reply)
    separators = ("থেকে", "হতে", "theke", "to", "→", "->")
    for source in potential_label_aliases(source_label):
        for target in potential_label_aliases(target_label):
            if any(f"{source}{separator}{target}" in text for separator in separators):
                return True
    return False


def reply_mentions_label(reply, label):
    text = normalize_direction_text(reply)
    tokens = re.findall(r"[a-z0-9]+|[\u0980-\u09ff]+", normalize_text(reply).replace("_", ""))
    token_set = set(tokens)
    for alias in potential_label_aliases(label):
        if alias in token_set or text == alias:
            return True
        if alias in {"প্রথম", "দ্বিতীয়", "দ্বিতীয়"} and alias in text:
            return True
    return False


def assess_potential_direction_reply(previous_question, student_reply):
    pair = potential_direction_pair(previous_question)
    if pair is None:
        return None

    high_label, low_label = pair
    expected_source, expected_target = (
        (low_label, high_label)
        if question_asks_negative_charge(previous_question)
        else (high_label, low_label)
    )
    wrong_source, wrong_target = expected_target, expected_source

    if reply_has_direction(student_reply, expected_source, expected_target):
        return True
    if reply_has_direction(student_reply, wrong_source, wrong_target):
        return False

    if reply_mentions_label(student_reply, expected_target) and not reply_mentions_label(student_reply, expected_source):
        return True
    if reply_mentions_label(student_reply, expected_source) and not reply_mentions_label(student_reply, expected_target):
        return False
    return None


def assess_understanding_reply(llm, chapter_name, lesson_name, concept, previous_question, student_reply):
    heuristic = classify_understanding_reply(student_reply)
    if heuristic is not None:
        return heuristic

    potential_direction = assess_potential_direction_reply(previous_question, student_reply)
    if potential_direction is not None:
        return potential_direction

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

    best_unused_image = None
    best_unused_score = 0
    best_overall_image = None
    best_overall_score = 0

    for image in images:
        image_id = str(image.get("image_id") or "").strip()
        if not image_id:
            continue

        score = score_image_relevance(hint, image)
        if score > best_overall_score:
            best_overall_score = score
            best_overall_image = image

        if image_id in excluded:
            continue
        if score > best_unused_score:
            best_unused_score = score
            best_unused_image = image

    best_image = None
    best_score = 0
    if best_unused_image is not None and best_unused_score > 0:
        best_image = best_unused_image
        best_score = best_unused_score
    elif best_overall_image is not None and best_overall_score >= IMAGE_REUSE_SCORE_THRESHOLD:
        best_image = best_overall_image
        best_score = best_overall_score

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


def append_image_descriptions_to_response(response_text, response_images):
    base = normalize_grounded_text(response_text)
    if not base:
        return ""
    if not isinstance(response_images, list) or not response_images:
        return base

    normalized_base = normalize_text(base)
    additions = []
    for image in response_images:
        description = normalize_grounded_text(image.get("description") or "")
        if not description:
            continue
        normalized_description = normalize_text(description)
        if normalized_description and normalized_description in normalized_base:
            continue
        additions.append(f"চিত্র সহায়তা: {description}")

    if not additions:
        return base
    return f"{base}\n\n" + "\n".join(additions)


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
    chunks = (retrieval.get("chunks") if isinstance(retrieval, dict) else []) or []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
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
    chunks = (retrieval.get("chunks") if isinstance(retrieval, dict) else []) or []
    chunk_text = "\n".join(str(chunk.get("chunk_text") or "") for chunk in chunks if isinstance(chunk, dict))
    if not needs_visual_image(user_text, chunk_text):
        return []

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
    extra_hint="",
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

    if not needs_visual_image(extra_hint):
        return []

    query_parts = [
        strip_topic_numbering(concept.get("section_label") or ""),
        str(concept.get("chunk_text") or "").strip(),
        str(extra_hint or "").strip(),
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


def build_lesson_completion_payload(concepts=None, used_image_ids=None):
    topic_labels = []
    for concept in concepts or []:
        label = strip_topic_numbering(concept.get("section_label") or "")
        if label and not is_generic_chunk_label(label):
            topic_labels.append(label)
        if len(topic_labels) >= 5:
            break

    if topic_labels:
        covered_text = "এই পাঠে আমরা কভার করেছি: " + ", ".join(topic_labels) + "।"
    else:
        covered_text = "এই পাঠের মূল অংশগুলো কভার করা হয়েছে।"

    response_text = (
        "পাঠ শেষ হয়েছে।\n\n"
        f"{covered_text}\n\n"
        "এখন তুমি চাইলে এই পাঠ থেকে ছোট অনুশীলন, সংক্ষিপ্ত রিভিশন, বা সন্দেহের প্রশ্ন করতে পারো।"
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
    next_step_hint="",
    extra_image_hint="",
):
    user_prompt = build_lesson_flow_prompt(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=concept,
        student_reply=student_reply,
        previous_question=previous_question,
        re_explain=re_explain,
    )
    metadata = {
        "chat_model": resolve_chat_model_id(chat_model),
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "concept_index": concept.get("concept_index"),
        "re_explain": re_explain,
    }
    messages = [
        SystemMessage(content=LESSON_FLOW_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        parsed = invoke_teaching_llm_for_json(
            llm,
            messages,
            context="simple_graph.teach_lesson_concept",
            metadata=metadata,
            retry_user_prompt=user_prompt,
        )
    except Exception as exc:
        raise ValueError(normalize_error_message(exc)) from exc

    check_question = avoid_repeated_check_question(
        parsed["check_question"],
        concept,
        previous_question,
        allow_repeat=re_explain,
    )
    base_response_markdown = compose_chat_markdown(
        parsed["textbook_answer"],
        parsed["extra_explanation"],
        [],
        check_question=check_question,
        next_step_hint=next_step_hint,
    )
    selected_images = select_images_for_concept(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=concept,
        response_text=base_response_markdown,
        used_image_ids=used_image_ids,
        extra_hint=extra_image_hint,
    )
    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=selected_images,
        response_text=base_response_markdown,
        chat_model=chat_model,
    )
    response_markdown = append_image_descriptions_to_response(base_response_markdown, response_images)
    response_markdown = apply_image_reference_policy(response_markdown, response_images)
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
            "last_question": check_question,
            "used_image_ids": updated_used_image_ids,
        },
        "textbook_answer": parsed["textbook_answer"],
        "extra_explanation": parsed["extra_explanation"],
        "check_question": check_question,
        "next_hint": next_step_hint,
        "citations": [],
    }


def answer_lesson_flow_question(
    llm,
    chapter_name,
    lesson_name,
    concept,
    student_question,
    previous_question="",
    chat_model=None,
    used_image_ids=None,
    next_step_hint="",
):
    user_prompt = build_lesson_flow_question_prompt(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=concept,
        student_question=student_question,
        previous_question=previous_question,
    )
    metadata = {
        "chat_model": resolve_chat_model_id(chat_model),
        "chapter_name": chapter_name,
        "lesson_name": lesson_name,
        "concept_index": concept.get("concept_index"),
    }
    messages = [
        SystemMessage(content=LESSON_FLOW_QUESTION_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        parsed = invoke_teaching_llm_for_json(
            llm,
            messages,
            context="simple_graph.answer_lesson_flow_question",
            metadata=metadata,
            retry_user_prompt=user_prompt,
        )
    except Exception as exc:
        raise ValueError(normalize_error_message(exc)) from exc

    practice_request = is_practice_request(student_question)
    if practice_request:
        check_question = remove_practice_answer_sections(parsed["check_question"]) or parsed["check_question"]
        textbook_answer, extra_explanation = build_practice_request_intro(concept)
    else:
        check_question = previous_question or parsed["check_question"]
        textbook_answer = parsed["textbook_answer"]
        extra_explanation = parsed["extra_explanation"]
    base_response_markdown = compose_chat_markdown(
        textbook_answer,
        extra_explanation,
        [],
        check_question=check_question,
        next_step_hint=next_step_hint,
    )
    selected_images = select_images_for_concept(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=concept,
        response_text=base_response_markdown,
        used_image_ids=used_image_ids,
        extra_hint=student_question,
    )
    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=selected_images,
        response_text=base_response_markdown,
        chat_model=chat_model,
    )
    response_markdown = append_image_descriptions_to_response(base_response_markdown, response_images)
    response_markdown = apply_image_reference_policy(response_markdown, response_images)
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
            "last_question": check_question,
            "used_image_ids": updated_used_image_ids,
        },
        "textbook_answer": textbook_answer,
        "extra_explanation": extra_explanation,
        "check_question": check_question,
        "next_hint": next_step_hint,
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
    current_next_step_hint = build_next_step_hint(concepts, concept_index)

    if flow_state["awaiting_understanding"] and not flow_state["lesson_complete"]:
        if is_student_question_in_lesson_flow(user_text):
            return answer_lesson_flow_question(
                llm=llm,
                chapter_name=chapter_name,
                lesson_name=lesson_name,
                concept=current_concept,
                student_question=user_text,
                previous_question=flow_state["last_question"],
                chat_model=chat_model,
                used_image_ids=flow_state["used_image_ids"],
                next_step_hint=current_next_step_hint,
            )

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
                return build_lesson_completion_payload(concepts=concepts, used_image_ids=flow_state["used_image_ids"])
            next_payload = teach_lesson_concept(
                llm=llm,
                chapter_name=chapter_name,
                lesson_name=lesson_name,
                concept=concepts[next_index],
                chat_model=chat_model,
                previous_question=flow_state["last_question"],
                used_image_ids=flow_state["used_image_ids"],
                next_step_hint=build_next_step_hint(concepts, next_index),
            )
            next_payload["response"] = prepend_lesson_feedback(
                next_payload.get("response"),
                "ঠিক ধরেছো। এবার সেই ধারণার উপর দাঁড়িয়ে পরের অংশে যাই।",
            )
            return next_payload

        retry_payload = teach_lesson_concept(
            llm=llm,
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            concept=current_concept,
            chat_model=chat_model,
            re_explain=True,
            student_reply=user_text,
            previous_question=flow_state["last_question"],
            used_image_ids=flow_state["used_image_ids"],
            next_step_hint=current_next_step_hint,
            extra_image_hint=user_text,
        )
        retry_payload["response"] = prepend_lesson_feedback(
            retry_payload.get("response"),
            "এখানে একটু গ্যাপ আছে। ভুল জায়গাটা ঠিক করে আবার দেখি।",
        )
        return retry_payload

    return teach_lesson_concept(
        llm=llm,
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        concept=current_concept,
        chat_model=chat_model,
        used_image_ids=flow_state["used_image_ids"],
        next_step_hint=current_next_step_hint,
    )


def run_grounded_chat(thread_id, chapter_name, lesson_name, lesson_catalog, history, user_text, chat_model=None):
    del thread_id, lesson_catalog

    llm = get_llm(chat_model)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(chat_model))

    prompt = build_study_chat_prompt(chapter_name, lesson_name, user_text)
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
    citations = []
    response_markdown = compose_chat_markdown(
        parsed["textbook_answer"],
        parsed["extra_explanation"],
        citations,
    )

    selected_images = select_images_for_reply(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        user_text=user_text,
        textbook_answer=parsed["textbook_answer"],
        extra_explanation=parsed["extra_explanation"],
        retrieval={},
    )
    response_images = resolve_images_for_response(
        chapter_name=chapter_name,
        lesson_name=lesson_name,
        selected_images=selected_images,
        response_text=response_markdown,
        chat_model=chat_model,
    )
    response_markdown = append_image_descriptions_to_response(response_markdown, response_images)
    response_markdown = apply_image_reference_policy(response_markdown, response_images)

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

    flow_state = normalize_lesson_flow_state(saved_thread_state)
    start_request = is_lesson_start_request(user_text)
    use_lesson_flow = (flow_state["mode"] == "lesson_flow" and not flow_state["lesson_complete"]) or (
        flow_state["lesson_complete"] and start_request
    ) or (
        flow_state["mode"] != "lesson_flow" and start_request
    )

    if use_lesson_flow:
        catalog = ensure_lesson_catalog(
            chapter_name=chapter_name,
            lesson_name=lesson_name,
            lesson_source=lesson_source,
            lesson_catalog=lesson_catalog,
        )
        if not catalog:
            raise ValueError("Lesson content is empty")

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
        lesson_catalog=[],
        history=history,
        user_text=user_text,
        chat_model=chat_model,
    )
