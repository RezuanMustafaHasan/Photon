import os

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="openai/gpt-oss-120b", api_key=GROQ_API_KEY) if GROQ_API_KEY else None

memory = MemorySaver()
initialized_threads = set()


class State(TypedDict):
    messages: Annotated[list, add_messages]


def chatbot(state: State):
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


def run_chat(thread_id, system_text, history, user_text):
    messages = []
    if thread_id not in initialized_threads:
        if system_text:
            messages.append(SystemMessage(content=system_text))
        messages.extend(build_history_messages(history or []))
        initialized_threads.add(thread_id)
    messages.append(HumanMessage(content=user_text))
    state = graph.invoke({"messages": messages}, config={"configurable": {"thread_id": thread_id}})
    last = state["messages"][-1]
    return last.content
