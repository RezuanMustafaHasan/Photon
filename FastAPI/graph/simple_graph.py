import json
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from graph.exam_generator import extract_json_text, extract_text_content, normalize_error_message
from graph.lesson_grounding import (
    lesson_source_label,
    normalize_lesson_key,
    retrieve_relevant_lesson_chunks,
    truncate_text,
)


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
    "- When you write formulas or symbols, always use Markdown math delimiters: inline $...$ and block $$...$$.\n"
    "- Do not write raw LaTeX commands like \\frac outside math delimiters.\n"
    "- Keep Bangla words outside the math delimiters whenever possible.\n"
    "- When listing formulas, prefer short markdown bullets and wrap each formula in $...$ or $$...$$.\n"
    "- Keep the tone simple, student-friendly, and concise.\n"
    "- Prefer Bangla if the lesson or student message is primarily Bangla; otherwise match the student's language."
)
MAX_HISTORY_ITEMS = 8


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key)


def compose_chat_markdown(textbook_answer, extra_explanation, citations):
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
    json_text = extract_json_text(raw_output)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The grounded chat JSON is malformed: {exc.msg}.") from exc

    if not isinstance(payload, dict):
        raise ValueError("The grounded chat payload must be a JSON object.")

    textbook_answer = str(payload.get("textbook_answer") or "").strip()
    extra_explanation = str(payload.get("extra_explanation") or "").strip()

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


def run_chat(thread_id, chapter_name, lesson_name, lesson_catalog, history, user_text):
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
    messages.extend(build_history_messages(history))
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
        "textbook_answer": parsed["textbook_answer"],
        "extra_explanation": parsed["extra_explanation"],
        "citations": citations,
    }
