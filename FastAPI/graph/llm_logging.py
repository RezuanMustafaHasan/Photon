import json
import os
from datetime import datetime, timezone


LOG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "llm_io.jsonl",
)


def _serialize_scalar(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _serialize_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): _serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]

    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _serialize_value(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "dict") and callable(value.dict):
        try:
            return _serialize_value(value.dict())
        except Exception:
            pass

    if hasattr(value, "content") or hasattr(value, "tool_calls"):
        payload = {
            "type": getattr(value, "type", value.__class__.__name__),
            "content": _serialize_value(getattr(value, "content", None)),
        }
        for attr in (
            "id",
            "name",
            "tool_calls",
            "invalid_tool_calls",
            "additional_kwargs",
            "response_metadata",
            "usage_metadata",
        ):
            attr_value = getattr(value, attr, None)
            if attr_value not in (None, [], {}, ""):
                payload[attr] = _serialize_value(attr_value)
        return payload

    return _serialize_scalar(value)


def _extract_model_name(llm):
    current = llm
    seen = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        for attr in ("model_name", "model"):
            model_name = getattr(current, attr, None)
            if isinstance(model_name, str) and model_name.strip():
                return model_name.strip()

        current = getattr(current, "bound", None)

    return ""


def _append_log(record):
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False))
        log_file.write("\n")


def invoke_llm_with_logging(llm, messages, context, metadata=None):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": str(context or "").strip(),
        "model": _extract_model_name(llm),
        "request": {
            "messages": _serialize_value(list(messages or [])),
            "metadata": _serialize_value(metadata or {}),
        },
    }

    try:
        response = llm.invoke(messages)
    except Exception as exc:
        record["status"] = "error"
        record["error"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
        _append_log(record)
        raise

    record["status"] = "ok"
    record["response"] = _serialize_value(response)
    _append_log(record)
    return response
