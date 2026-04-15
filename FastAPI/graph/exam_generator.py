import json
import os
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from graph.llm_logging import invoke_llm_with_logging


EXAM_SYSTEM_PROMPT = (
    "You generate multiple-choice exams for Bangladeshi HSC Physics students.\n"
    "Use only the provided lesson content.\n"
    "Return valid JSON only. Do not include markdown, commentary, or code fences.\n"
    "Every question must be answerable from the provided lesson content.\n"
    "Prefer Bangla when the source lessons are primarily Bangla, otherwise match the lesson language.\n"
    "Create plausible distractors, avoid repeated questions, and never use 'all of the above' or 'none of the above'.\n"
    "Use clean exam formatting: keep questions concise, keep options short, and avoid noisy prefixes like 'Question:' or 'Option A:'.\n"
    "When mathematical symbols, vectors, subscripts, superscripts, fractions, equations, or units need formatting, use LaTeX.\n"
    "Use inline LaTeX with $...$ for inline math and $$...$$ only for standalone equations.\n"
    "For multiplied units or symbols, use LaTeX operators like \\cdot and \\times inside math, not Unicode characters like · or ×.\n"
    "When writing units such as newton-meter, prefer $N \\cdot m$ instead of text like N·m inside math.\n"
    "Do not output escaped math delimiters like \\(...\\) or \\[...\\]."
)


def get_exam_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key)


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


def build_exam_prompt(selected_lessons, question_count, previous_error=None, previous_output=None):
    lesson_context = json.dumps(selected_lessons, ensure_ascii=False)
    prompt = (
        f"Generate exactly {question_count} MCQ questions.\n"
        "Return JSON with this exact schema:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "chapter_name": "chapter title exactly as provided in the lesson context",\n'
        '      "topic_name": "topic title exactly as provided in the lesson context",\n'
        '      "question": "question text",\n'
        '      "options": ["option 1", "option 2", "option 3", "option 4"],\n'
        '      "correct_option_index": 0\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        f"- The JSON must contain exactly {question_count} questions.\n"
        "- Each question must have exactly 4 non-empty options.\n"
        "- correct_option_index must be an integer from 0 to 3.\n"
        "- Use chapter_name and topic_name exactly from the provided lesson context.\n"
        "- Cover the selected lessons as evenly as possible.\n"
        "- Do not repeat the same question.\n"
        "- Do not mention that the content came from a lesson.\n"
        "- Keep each option to a single concise statement, not a paragraph.\n"
        "- Do not prefix options with A, B, C, D, numbers, bullets, or labels like 'Option'.\n"
        "- Do not prefix questions with labels like 'Q', 'Question', or numbering.\n"
        "- Use $...$ for inline formulas, vectors, subscripts, superscripts, Greek symbols, and equations.\n"
        "- Use $$...$$ only when a full equation needs display formatting on its own line.\n"
        "- Use \\cdot and \\times for multiplied units or terms inside math instead of Unicode symbols like · or ×.\n"
        "- Never output raw escaped delimiters like \\(...\\) or \\[...\\].\n"
        "- Avoid markdown headings, tables, code fences, and decorative symbols.\n"
        "- Output JSON only.\n\n"
        f"Lesson context:\n{lesson_context}"
    )

    if previous_error:
        prompt += (
            "\n\nThe previous response was invalid.\n"
            f"Validation error: {previous_error}\n"
            "Fix the JSON and regenerate the full response from scratch."
        )
        if previous_output:
            prompt += f"\nPrevious invalid response:\n{previous_output}"

    return prompt


def extract_json_text(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("The AI returned an empty response.")

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        return text[object_start:object_end + 1]

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        return text[array_start:array_end + 1]

    raise ValueError("The AI response did not contain valid JSON.")


def normalize_title(value):
    return str(value or "").strip().lower()


def normalize_math_delimiters(text):
    return (
        str(text or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\\[", "[[DISPLAY_MATH_OPEN]]")
        .replace("\\]", "[[DISPLAY_MATH_CLOSE]]")
        .replace("\\(", "[[INLINE_MATH_OPEN]]")
        .replace("\\)", "[[INLINE_MATH_CLOSE]]")
        .replace("[[DISPLAY_MATH_OPEN]]", "$$")
        .replace("[[DISPLAY_MATH_CLOSE]]", "$$")
        .replace("[[INLINE_MATH_OPEN]]", "$")
        .replace("[[INLINE_MATH_CLOSE]]", "$")
    )


def strip_common_prefixes(text, is_option=False):
    cleaned = str(text or "").strip()
    if is_option:
        cleaned = re.sub(r"^\s*(?:[-*•]\s+|(?:option|choice)\s*[A-Da-d0-9]+[:.)-]?\s*|[A-Da-d][.)-]\s+|[0-9]+[.)-]\s+)", "", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = re.sub(r"^\s*(?:question|ques|q)\s*[:.)-]?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^\s*[0-9]+[.)-]\s*", "", cleaned)
    return cleaned.strip()


def sanitize_generated_text(text, is_option=False):
    cleaned = extract_text_content(text)
    cleaned = normalize_math_delimiters(cleaned)
    cleaned = strip_common_prefixes(cleaned, is_option=is_option)
    cleaned = cleaned.strip().strip('"').strip("'").strip("`")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    if is_option:
        cleaned = re.sub(r"\s*\n\s*", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
    else:
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

    return cleaned.strip()


def normalize_error_message(exc):
    message = str(exc or "").strip() or "Exam generation failed."
    lowered = message.lower()

    if "rate_limit_exceeded" in lowered or "tokens per minute" in lowered or "request too large" in lowered:
        return "Selected content is too large for the current AI limit. Try fewer topics or fewer questions."
    if "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return "The AI service API key is invalid or unavailable."
    if "timeout" in lowered:
        return "The AI service timed out while generating the exam. Please try again."

    return message


def parse_questions_payload(raw_text, selected_lessons, question_count):
    json_text = extract_json_text(raw_text)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The AI returned malformed JSON: {exc.msg}.") from exc

    if isinstance(payload, list):
        questions = payload
    elif isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        questions = payload.get("questions")
    else:
        raise ValueError("The AI JSON must contain a 'questions' array.")

    if len(questions) != question_count:
        raise ValueError(f"Expected {question_count} questions but received {len(questions)}.")

    selected_topic_map = {}
    for lesson in selected_lessons:
        chapter_key = normalize_title(lesson.get("chapter_name"))
        topic_key = normalize_title(lesson.get("topic_name"))
        selected_topic_map[(chapter_key, topic_key)] = {
            "chapterName": lesson.get("chapter_name"),
            "topicName": lesson.get("topic_name"),
        }

    parsed_questions = []
    seen_questions = set()

    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question {index} is not a JSON object.")

        chapter_name = str(item.get("chapter_name") or item.get("chapterName") or "").strip()
        topic_name = str(item.get("topic_name") or item.get("topicName") or "").strip()
        question_text = sanitize_generated_text(item.get("question") or "")
        options = item.get("options")
        correct_option_index = item.get("correct_option_index")
        if correct_option_index is None:
            correct_option_index = item.get("correctOptionIndex")

        if not chapter_name or not topic_name or not question_text:
            raise ValueError(f"Question {index} is missing chapter_name, topic_name, or question text.")

        topic_key = (normalize_title(chapter_name), normalize_title(topic_name))
        if topic_key not in selected_topic_map:
            raise ValueError(
                f"Question {index} references an unknown lesson pair: {chapter_name} / {topic_name}."
            )

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Question {index} must contain exactly 4 options.")

        cleaned_options = [sanitize_generated_text(option or "", is_option=True) for option in options]
        if any(not option for option in cleaned_options):
            raise ValueError(f"Question {index} contains an empty option.")

        if len({normalize_title(option) for option in cleaned_options}) != 4:
            raise ValueError(f"Question {index} contains duplicate options.")

        try:
            correct_option_index = int(correct_option_index)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Question {index} has an invalid correct_option_index.") from exc

        if correct_option_index < 0 or correct_option_index > 3:
            raise ValueError(f"Question {index} has a correct_option_index outside 0-3.")

        normalized_question = normalize_title(question_text)
        if normalized_question in seen_questions:
            raise ValueError(f"Question {index} is duplicated.")
        seen_questions.add(normalized_question)

        canonical_topic = selected_topic_map[topic_key]
        parsed_questions.append(
            {
                "id": uuid.uuid4().hex,
                "chapterName": canonical_topic["chapterName"],
                "topicName": canonical_topic["topicName"],
                "question": question_text,
                "options": cleaned_options,
                "correctOptionIndex": correct_option_index,
            }
        )

    return parsed_questions


def generate_exam(selected_lessons, question_count):
    llm = get_exam_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")

    last_error = None
    previous_output = None

    for _ in range(2):
        prompt = build_exam_prompt(
            selected_lessons=selected_lessons,
            question_count=question_count,
            previous_error=last_error,
            previous_output=previous_output,
        )
        messages = [
            SystemMessage(content=EXAM_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        try:
            response = invoke_llm_with_logging(
                llm,
                messages,
                context="exam_generator.generate_exam",
                metadata={
                    "question_count": question_count,
                    "attempt": 2 if last_error else 1,
                },
            )
        except Exception as exc:
            raise ValueError(normalize_error_message(exc)) from exc
        raw_output = extract_text_content(response.content)

        try:
            return parse_questions_payload(raw_output, selected_lessons, question_count)
        except ValueError as exc:
            last_error = str(exc)
            previous_output = raw_output

    raise ValueError(last_error or "Exam generation failed.")
