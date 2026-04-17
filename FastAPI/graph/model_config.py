import os


DEFAULT_CHAT_MODEL = "groq:openai/gpt-oss-120b"
DEFAULT_CHAT_MODEL_CONFIG = {
    "id": DEFAULT_CHAT_MODEL,
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
}


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


def get_llm(selected_model=None, max_tokens=None):
    model_config = resolve_chat_model_config(selected_model)
    llm_kwargs = {"temperature": 0}
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = int(max_tokens)

    if model_config["provider"] == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            from langchain_openai import ChatOpenAI
        except (ImportError, ModuleNotFoundError) as exc:
            raise ValueError("langchain-openai is not installed") from exc

        return ChatOpenAI(model=model_config["model"], api_key=api_key, **llm_kwargs)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from langchain_groq import ChatGroq
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError("langchain-groq is not installed") from exc

    return ChatGroq(model=model_config["model"], api_key=api_key, **llm_kwargs)
