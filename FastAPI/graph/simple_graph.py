import json
import os
import re

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq


memory = MemorySaver()
initialized_threads = set()
lesson_image_loader = None
IMAGE_TOOL_NAME = "fetch_relevant_lesson_images"

BASE_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "Understand these concepts in very simple language, so that student can catch the concepts very easily.\n"
    "Don't reply all at once. Understand student a small concept. Then judge him asking a very small conceptual question. Then move next.\n"
    "Student might ask question, answer them, but after that move to the next topic in the lesson. Cover the full lesson.\n"
    "Use the examples, terminology, terms same as provided in the lesson text.\n"
    "Only cover the concepts in the lesson text. Don't cover any other concept, Not even the extension of the concept. No extra formula or something.\n"
    "If the overall lesson is done, just simply reply \"Done\". Then the student might ask any additional question.\n"
    "When a visual explanation would help the student understand a concept better, call the tool fetch_relevant_lesson_images.\n"
    "Only call that tool when needed and only with the current chapter and lesson names.\n"
    "If the tool returns images, use their descriptions/topics in your explanation and assume the UI will show those images automatically.\n"
    "Do not output markdown image tags or raw URLs in the reply body."
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def configure_image_loader(loader):
    global lesson_image_loader
    lesson_image_loader = loader


def get_llm():
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


def normalize_text(value):
    return str(value or "").strip().lower()


def tokenize(value):
    return set(re.findall(r"[a-z0-9\u0980-\u09ff]+", normalize_text(value)))


def parse_json_from_text(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        return None

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


def normalize_topics(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    return []


def normalize_image_record(item):
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
        "imageURL": image_url,
        "description": description,
        "topic": topics,
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


def score_image_relevance(query_text, image):
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return 0

    description_tokens = tokenize(image.get("description"))
    topic_tokens = set()
    exact_topic_hits = 0

    for topic in image.get("topic") or []:
        topic_tokens.update(tokenize(topic))
        if normalize_text(topic) and normalize_text(topic) in normalize_text(query_text):
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

    # If the student explicitly asks for a diagram/image, provide a fallback visual.
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
    for item in raw_images:
        image = normalize_image_record(item)
        if image:
            normalized.append(image)

    return normalized


@tool(IMAGE_TOOL_NAME)
def fetch_relevant_lesson_images(chapter_name: str, lesson_name: str, query: str, max_images: int = 2) -> str:
    """Load lesson images from MongoDB and return only images relevant to the current explanation."""
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
    reason = "No relevant image matched this question."
    if selected_images:
        reason = "Relevant images selected based on topic/description overlap."

    return json.dumps(
        {
            "selected_images": selected_images,
            "reason": reason,
            "total_images": len(images),
        },
        ensure_ascii=False,
    )


def assistant(state: State):
    llm = get_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")

    llm_with_tools = llm.bind_tools([fetch_relevant_lesson_images])
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


builder = StateGraph(State)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode([fetch_relevant_lesson_images]))
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")
graph = builder.compile(checkpointer=memory)


def normalize_images_for_response(raw_images):
    if not isinstance(raw_images, list):
        return []

    normalized = []
    for item in raw_images:
        image = normalize_image_record(item)
        if image:
            normalized.append(image)

    return normalized


def build_history_messages(history):
    messages = []
    for item in history:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = extract_text_content(item.get("content"))
        if not content:
            continue

        if role == "assistant":
            history_images = normalize_images_for_response(item.get("images") or [])
            if history_images:
                image_notes = []
                for image in history_images[:2]:
                    description = image.get("description")
                    topics = ", ".join(image.get("topic") or [])
                    note = "Previous attached image"
                    if description:
                        note += f": {description}"
                    if topics:
                        note += f" | topics: {topics}"
                    image_notes.append(note)
                if image_notes:
                    content = f"{content}\n\n" + "\n".join(f"- {note}" for note in image_notes)

            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    return messages


def extract_images_from_messages(messages):
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", "") != IMAGE_TOOL_NAME:
            continue

        payload = parse_json_from_text(extract_text_content(message.content))
        if not isinstance(payload, dict):
            continue

        selected = normalize_images_for_response(payload.get("selected_images") or [])
        if selected:
            return selected

    return []


def run_chat(thread_id, chapter_name, lesson_name, lesson_text, history, user_text):
    messages = []
    if thread_id not in initialized_threads:
        combined = BASE_PROMPT
        if lesson_text:
            combined = (
                f"{BASE_PROMPT}\n\n"
                f"Current chapter: {chapter_name}\n"
                f"Current lesson: {lesson_name}\n\n"
                f"Lesson:\n{lesson_text}"
            )

        messages.append(SystemMessage(content=combined))
        messages.extend(build_history_messages(history or []))
        initialized_threads.add(thread_id)

    messages.append(HumanMessage(content=user_text))
    state = graph.invoke({"messages": messages}, config={"configurable": {"thread_id": thread_id}})
    last = state["messages"][-1]
    response_text = extract_text_content(getattr(last, "content", ""))
    images = extract_images_from_messages(state.get("messages") or [])
    return {
        "response": response_text,
        "images": images,
    }