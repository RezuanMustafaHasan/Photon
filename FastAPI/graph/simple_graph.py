import os

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
memory = MemorySaver()
initialized_threads = set()
BASE_PROMPT = (
    "You are a Bangladeshi HSC physics tutor.\n"
    "Understand these concepts in very simple language, so that student can catch the concepts very easily.\n"
    "Don't reply all at once. Understand student a small concept. Then judge him asking a very small conceptual question. Then move next.\n"
    "Student might ask question, answer them, but after that move to the next topic in the lesson. Cover the full lesson.\n"
    "Use the examples, terminology, terms same as provided in the lesson text.\n"
    "Only cover the concepts in the lesson text. Don't cover any other concept, Not even the extension of the concept. No extra formula or something.\n"
    "If the overall lesson is done, just simply reply \"Done\". Then the student might ask any additional question."
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(model="openai/gpt-oss-120b", api_key=api_key)


def chatbot(state: State):
    llm = get_llm()
    if llm is None:
        raise ValueError("GROQ_API_KEY is not set")
    return {"messages": [llm.invoke(state["messages"])]}


builder = StateGraph(State)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)
graph = builder.compile(checkpointer=memory)


def build_history_messages(history):
    messages = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


def run_chat(thread_id, lesson_text, history, user_text):
    messages = []
    if thread_id not in initialized_threads:
        combined = BASE_PROMPT
        if lesson_text:
            combined = f"{BASE_PROMPT}\n\nLesson:\n{lesson_text}"
        messages.append(SystemMessage(content=combined))
        messages.extend(build_history_messages(history or []))
        initialized_threads.add(thread_id)
    messages.append(HumanMessage(content=user_text))
    state = graph.invoke({"messages": messages}, config={"configurable": {"thread_id": thread_id}})
    last = state["messages"][-1]
    return last.content
