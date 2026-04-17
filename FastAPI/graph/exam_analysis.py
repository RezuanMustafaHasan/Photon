import json

from pydantic import ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from graph.exam_generator import extract_json_text, extract_text_content, get_exam_llm, normalize_error_message
from graph.llm_logging import invoke_llm_with_logging
from graph.model_config import get_missing_chat_model_key_message, resolve_chat_model_id


ANALYSIS_SYSTEM_PROMPT = (
    "You analyze completed Bangladeshi HSC Physics MCQ exams.\n"
    "Use only the provided finished exam data.\n"
    "Return valid JSON only, with no markdown or code fences.\n"
    "Focus on weaknesses, missed concepts, and actionable revision guidance.\n"
    "Prefer Bangla when the source questions are primarily Bangla, otherwise match the source language.\n"
    "Keep the summary concise, student-friendly, and specific to the wrong answers."
)


def build_exam_analysis_prompt(payload_json):
    return (
        "Analyze this completed exam attempt and return JSON with this exact schema:\n"
        "{\n"
        '  "headline": "short title",\n'
        '  "overallComment": "2-3 sentence overall takeaway",\n'
        '  "weaknesses": ["weakness 1", "weakness 2"],\n'
        '  "recommendedTopics": [\n'
        "    {\n"
        '      "chapterName": "chapter title from selections",\n'
        '      "topicName": "topic title from selections",\n'
        '      "reason": "why this topic should be revised"\n'
        "    }\n"
        "  ],\n"
        '  "studyAdvice": ["tip 1", "tip 2"]\n'
        "}\n"
        "Rules:\n"
        "- Base the analysis on the student's wrong answers only.\n"
        "- If the student got everything correct, celebrate that and provide maintenance advice.\n"
        "- recommendedTopics must use chapterName/topicName that appear in the provided selections or wrong questions.\n"
        "- Avoid generic filler.\n"
        "- Output JSON only.\n\n"
        f"Completed exam payload:\n{payload_json}"
    )


def validate_summary_payload(payload, SummaryModel):
    if not isinstance(payload, dict):
        raise ValueError("The AI summary payload must be a JSON object.")

    try:
        return SummaryModel(**payload)
    except ValidationError as exc:
        raise ValueError(f"The AI summary payload is invalid: {exc.errors()}.") from exc


def analyze_exam_attempt(payload, SummaryModel, selected_model=None):
    llm = get_exam_llm(selected_model)
    if llm is None:
        raise ValueError(get_missing_chat_model_key_message(selected_model))

    payload_json = json.dumps(payload, ensure_ascii=False)
    prompt = build_exam_analysis_prompt(payload_json)
    messages = [
        SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = invoke_llm_with_logging(
            llm,
            messages,
            context="exam_analysis.analyze_exam_attempt",
            metadata={
                "selection_count": len(payload.get("selections") or []),
                "question_count": payload.get("questionCount"),
                "chat_model": resolve_chat_model_id(selected_model),
            },
        )
    except Exception as exc:
        raise ValueError(normalize_error_message(exc)) from exc

    raw_output = extract_text_content(response.content)
    json_text = extract_json_text(raw_output)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"The AI summary JSON is malformed: {exc.msg}.") from exc

    summary = validate_summary_payload(parsed, SummaryModel)
    return summary.model_dump()
