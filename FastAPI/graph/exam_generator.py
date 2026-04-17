import json
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from graph.llm_logging import invoke_llm_with_logging
from graph.model_config import (
    get_llm,
    get_missing_chat_model_key_message,
    resolve_chat_model_id,
)


EXAM_SYSTEM_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "Your job is to create multiple-choice quizzes for Bangladeshi HSC Physics students.\n"
    "Return valid JSON only. Do not include markdown, commentary, or code fences.\n"
    "Use the provided chapter and topic names to create syllabus-aligned questions.\n"
    "Prefer Bangla when the provided topic names are primarily Bangla, otherwise match the topic language.\n"
    "Create plausible distractors, avoid repeated questions, and never use 'all of the above' or 'none of the above'.\n"
    "Use clean exam formatting: keep questions concise, keep options short, and avoid noisy prefixes like 'Question:' or 'Option A:'.\n"
    "When mathematical symbols, vectors, subscripts, superscripts, fractions, equations, or units need formatting, use LaTeX.\n"
    "Use inline LaTeX with $...$ for inline math and $$...$$ only for standalone equations.\n"
    "For multiplied units or symbols, use LaTeX operators like \\cdot and \\times inside math, not Unicode characters like · or ×.\n"
    "When writing units such as newton-meter, prefer $N \\cdot m$ instead of text like N·m inside math.\n"
    "Do not output escaped math delimiters like \\(...\\) or \\[...\\]."
)
EXAM_MAX_TOKENS_MIN = 4096
EXAM_MAX_TOKENS_MAX = 16000
EXAM_TOKENS_PER_QUESTION = 500
EXAM_MAX_QUESTIONS_PER_BATCH = 5


def resolve_exam_max_tokens(question_count):
    try:
        count = int(question_count)
    except (TypeError, ValueError):
        count = 1

    estimated = max(EXAM_MAX_TOKENS_MIN, count * EXAM_TOKENS_PER_QUESTION)
    return min(EXAM_MAX_TOKENS_MAX, estimated)


def get_exam_llm(selected_model=None, question_count=None):
    return get_llm(selected_model, max_tokens=resolve_exam_max_tokens(question_count))


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


def group_selected_topics(selected_topics):
    grouped = []
    chapter_map = {}

    for topic in selected_topics:
        chapter_name = str(topic.get("chapter_name") or "").strip()
        topic_name = str(topic.get("topic_name") or "").strip()
        if not chapter_name or not topic_name:
            continue

        if chapter_name not in chapter_map:
            chapter_map[chapter_name] = {
                "chapter_name": chapter_name,
                "topics": [],
            }
            grouped.append(chapter_map[chapter_name])

        if topic_name not in chapter_map[chapter_name]["topics"]:
            chapter_map[chapter_name]["topics"].append(topic_name)

    return grouped


def distribute_questions_across_topics(selected_topics, question_count):
    topics = [topic for topic in selected_topics if topic.get("chapter_name") and topic.get("topic_name")]
    if not topics:
        return []

    try:
        total_questions = int(question_count)
    except (TypeError, ValueError):
        total_questions = 0

    base_count = total_questions // len(topics)
    remainder = total_questions % len(topics)
    allocations = []

    for index, topic in enumerate(topics):
        assigned_count = base_count + (1 if index < remainder else 0)
        if assigned_count <= 0:
            continue
        allocations.append(
            {
                "chapter_name": topic["chapter_name"],
                "topic_name": topic["topic_name"],
                "question_count": assigned_count,
            }
        )

    return allocations


def build_exam_batches(selected_topics, question_count):
    batches = []

    for allocation in distribute_questions_across_topics(selected_topics, question_count):
        remaining = allocation["question_count"]
        while remaining > 0:
            batch_count = min(EXAM_MAX_QUESTIONS_PER_BATCH, remaining)
            batches.append(
                {
                    "selected_topics": [
                        {
                            "chapter_name": allocation["chapter_name"],
                            "topic_name": allocation["topic_name"],
                        }
                    ],
                    "question_count": batch_count,
                }
            )
            remaining -= batch_count

    return batches


def build_exam_prompt(selected_topics, question_count, previous_error=None, previous_output=None, excluded_questions=None):
    grouped_topics = group_selected_topics(selected_topics)
    chapter_names = [entry["chapter_name"] for entry in grouped_topics]
    topic_names = [
        topic_name
        for entry in grouped_topics
        for topic_name in entry["topics"]
    ]
    topic_context = json.dumps(grouped_topics, ensure_ascii=False)
    prompt = (
        "You are a Bangladeshi HSC physics tutor. Your job is to create a quiz.\n"
        f"Number of questions: {question_count}\n"
        f"Chapters: {json.dumps(chapter_names, ensure_ascii=False)}\n"
        f"Topics: {json.dumps(topic_names, ensure_ascii=False)}\n\n"
        f"Generate exactly {question_count} MCQ questions.\n"
        "Return JSON with this exact schema:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "chapter_name": "chapter title exactly as provided in the selected topics",\n'
        '      "topic_name": "topic title exactly as provided in the selected topics",\n'
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
        "- Use chapter_name and topic_name exactly from the provided selected topics.\n"
        "- Cover the selected topics as evenly as possible.\n"
        "- Do not repeat the same question.\n"
        "- Keep the quiz aligned with Bangladeshi HSC Physics.\n"
        "- Keep each option to a single concise statement, not a paragraph.\n"
        "- Keep every question and option short enough that the full quiz fits in one JSON response.\n"
        "- Do not prefix options with A, B, C, D, numbers, bullets, or labels like 'Option'.\n"
        "- Do not prefix questions with labels like 'Q', 'Question', or numbering.\n"
        "- Use $...$ for inline formulas, vectors, subscripts, superscripts, Greek symbols, and equations.\n"
        "- Use $$...$$ only when a full equation needs display formatting on its own line.\n"
        "- Use \\cdot and \\times for multiplied units or terms inside math instead of Unicode symbols like · or ×.\n"
        "- Never output raw escaped delimiters like \\(...\\) or \\[...\\].\n"
        "- Avoid markdown headings, tables, code fences, and decorative symbols.\n"
        "- Output JSON only.\n\n"
        f"Selected chapter/topic context:\n{topic_context}"
    )

    if excluded_questions:
        prompt += (
            "\n\nAlready used question texts to avoid repeating:\n"
            f"{json.dumps(list(excluded_questions), ensure_ascii=False)}"
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
        return "Selected exam data is too large for the current AI limit. Try fewer topics or fewer questions."
    if "api key" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return "The AI service API key is invalid or unavailable."
    if "timeout" in lowered:
        return "The AI service timed out while generating the exam. Please try again."

    return message


def get_finish_reason(response):
    metadata = getattr(response, "response_metadata", None) or {}
    finish_reason = metadata.get("finish_reason")
    if isinstance(finish_reason, str):
        return finish_reason.strip().lower()
    return ""


def is_length_limited_response(response):
    return get_finish_reason(response) == "length"


def dedupe_previous_output(previous_output, limit=1200):
    text = str(previous_output or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def parse_questions_payload(raw_text, selected_topics, question_count):
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
    for topic in selected_topics:
        chapter_key = normalize_title(topic.get("chapter_name"))
        topic_key = normalize_title(topic.get("topic_name"))
        selected_topic_map[(chapter_key, topic_key)] = {
            "chapterName": topic.get("chapter_name"),
            "topicName": topic.get("topic_name"),
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
                f"Question {index} references an unknown selected topic pair: {chapter_name} / {topic_name}."
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


def generate_exam_batch(selected_topics, question_count, selected_model=None, excluded_questions=None):
    llm = get_exam_llm(selected_model, question_count)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(selected_model))

    last_error = None
    previous_output = None

    for _ in range(2):
        prompt = build_exam_prompt(
            selected_topics=selected_topics,
            question_count=question_count,
            previous_error=last_error,
            previous_output=dedupe_previous_output(previous_output),
            excluded_questions=excluded_questions,
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
                    "selection_count": len(selected_topics),
                    "attempt": 2 if last_error else 1,
                    "chat_model": resolve_chat_model_id(selected_model),
                },
            )
        except Exception as exc:
            raise ValueError(normalize_error_message(exc)) from exc

        if is_length_limited_response(response):
            last_error = (
                "The AI response was cut off before finishing the exam JSON. "
                "Regenerate the entire quiz from scratch and keep each question and option shorter."
            )
            previous_output = None
            continue

        raw_output = extract_text_content(response.content)

        try:
            return parse_questions_payload(raw_output, selected_topics, question_count)
        except ValueError as exc:
            if is_length_limited_response(response):
                last_error = (
                    "The AI response was cut off before finishing the exam JSON. "
                    "Try fewer questions or another model if this keeps happening."
                )
                previous_output = None
                continue
            last_error = str(exc)
            previous_output = raw_output

    if last_error and "cut off before finishing the exam json" in last_error.lower():
        raise ValueError("The AI response was cut off before finishing the exam JSON. Try fewer questions or another model.")

    raise ValueError(last_error or "Exam generation failed.")


def interleave_questions_by_topic(questions, selected_topics):
    ordered_topic_keys = []
    seen = set()
    for topic in selected_topics:
        key = (normalize_title(topic.get("chapter_name")), normalize_title(topic.get("topic_name")))
        if key in seen:
            continue
        seen.add(key)
        ordered_topic_keys.append(key)

    grouped = {key: [] for key in ordered_topic_keys}
    extras = []

    for question in questions:
        key = (normalize_title(question.get("chapterName")), normalize_title(question.get("topicName")))
        if key in grouped:
            grouped[key].append(question)
        else:
            extras.append(question)

    interleaved = []
    while any(grouped[key] for key in ordered_topic_keys):
        for key in ordered_topic_keys:
            if grouped[key]:
                interleaved.append(grouped[key].pop(0))

    interleaved.extend(extras)
    return interleaved


def validate_unique_questions(questions):
    seen = set()
    for index, question in enumerate(questions, start=1):
        normalized_question = normalize_title(question.get("question"))
        if normalized_question in seen:
            raise ValueError(f"Question {index} is duplicated across batches.")
        seen.add(normalized_question)


def generate_exam(selected_topics, question_count, selected_model=None):
    batches = build_exam_batches(selected_topics, question_count)
    if not batches:
        return []

    generated_questions = []
    excluded_questions = []

    for batch in batches:
        batch_questions = generate_exam_batch(
            batch["selected_topics"],
            batch["question_count"],
            selected_model,
            excluded_questions=excluded_questions,
        )
        generated_questions.extend(batch_questions)
        excluded_questions.extend(question["question"] for question in batch_questions if question.get("question"))

    if len(generated_questions) != question_count:
        raise ValueError(f"Expected {question_count} questions but received {len(generated_questions)}.")

    validate_unique_questions(generated_questions)
    return interleave_questions_by_topic(generated_questions, selected_topics)
