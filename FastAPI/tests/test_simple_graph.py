import sys
import types
import unittest
from unittest.mock import patch

try:
    import langchain_core.messages  # noqa: F401
    import langchain_groq  # noqa: F401
except ModuleNotFoundError:
    langchain_core_module = types.ModuleType("langchain_core")
    langchain_core_messages = types.ModuleType("langchain_core.messages")

    class _BaseMessage:
        def __init__(self, content):
            self.content = content

    langchain_core_messages.AIMessage = _BaseMessage
    langchain_core_messages.HumanMessage = _BaseMessage
    langchain_core_messages.SystemMessage = _BaseMessage
    langchain_core_module.messages = langchain_core_messages

    langchain_groq_module = types.ModuleType("langchain_groq")

    class _FakeChatGroq:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def invoke(self, _messages):
            raise RuntimeError("ChatGroq stub should not be invoked directly in tests")

    langchain_groq_module.ChatGroq = _FakeChatGroq

    sys.modules["langchain_core"] = langchain_core_module
    sys.modules["langchain_core.messages"] = langchain_core_messages
    sys.modules["langchain_groq"] = langchain_groq_module

from graph.simple_graph import compose_chat_markdown, parse_grounded_response, run_chat


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return type("FakeResponse", (), {"content": self.content})()


SAMPLE_LESSON = {
    "chapter_name": "Static Electricity",
    "lesson_name": "Coulomb's Law",
    "content": """
Page 1
## Coulomb's Law

দুটি চার্জের মধ্যবর্তী তড়িৎ বল দূরত্বের বর্গের ব্যস্তানুপাতিক।

### Formula

F = kq1q2 / r^2
""",
}

SECOND_LESSON = {
    "chapter_name": "Static Electricity",
    "lesson_name": "Electric Field",
    "content": """
Page 2
## Electric Field

তড়িৎ ক্ষেত্র হলো চার্জের চারপাশের সেই অঞ্চল যেখানে অন্য চার্জ বল অনুভব করে।
""",
}


class SimpleGraphTests(unittest.TestCase):
    def test_compose_chat_markdown_includes_sections_and_sources(self):
        output = compose_chat_markdown(
            "This comes from the lesson.",
            "This is extra intuition.",
            [
                {
                    "section_label": "Page 1 / Coulomb's Law",
                    "snippet": "Force is inversely proportional to r^2.",
                }
            ],
        )

        self.assertIn("From your lesson", output)
        self.assertIn("Extra explanation", output)
        self.assertIn("Sources", output)

    @patch("graph.simple_graph.get_llm")
    def test_run_chat_returns_structured_grounded_payload(self, mock_get_llm):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"দূরত্ব বাড়লে বল কমে যায় কারণ এটি r^2 এর ব্যস্তানুপাতিক।","extra_explanation":"সহজভাবে বললে, দূরে গেলে চার্জের প্রভাব ছড়িয়ে পড়ে।"}'
        )

        result = run_chat(
            "thread-1",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [],
            "দূরত্ব বাড়লে বল কেন কমে যায়?",
        )

        self.assertIn("textbook_answer", result)
        self.assertIn("extra_explanation", result)
        self.assertIn("citations", result)
        self.assertEqual(result["citations"], [])
        self.assertIn("From your lesson", result["response"])

    @patch("graph.simple_graph.get_llm")
    def test_run_chat_allows_extra_section_for_outside_lesson_question(self, mock_get_llm):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"এই নির্দিষ্ট particle accelerator topic টি বর্তমান lesson-এ নেই।","extra_explanation":"Particle accelerators charged particles কে electric field দিয়ে ত্বরিত করে।"}'
        )

        result = run_chat(
            "thread-2",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [],
            "particle accelerator এ electric field কীভাবে কাজ করে?",
        )

        self.assertIn("lesson", result["textbook_answer"].lower())
        self.assertIn("particle accelerators", result["extra_explanation"].lower())

    @patch("graph.simple_graph.get_llm")
    def test_run_chat_adds_source_only_for_cross_lesson_match(self, mock_get_llm):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"তড়িৎ ক্ষেত্রের ধারণাটি এই অধ্যায়ের Electric Field lesson-এ সরাসরি বোঝানো হয়েছে।","extra_explanation":"সহজভাবে বললে, চার্জের আশেপাশের প্রভাবিত অঞ্চলই electric field।"}'
        )

        result = run_chat(
            "thread-3",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [],
            "electric field কী?",
        )

        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["lesson_name"], "Electric Field")
        self.assertEqual(result["citations"][0]["snippet"], "")

    def test_parse_grounded_response_repairs_unescaped_latex_commands(self):
        parsed = parse_grounded_response(
            r'{"textbook_answer":"\tau = rF\sin\theta","extra_explanation":"\text{Unit} = \text{N·m}"}'
        )

        self.assertEqual(parsed["textbook_answer"], r"\tau = rF\sin\theta")
        self.assertEqual(parsed["extra_explanation"], r"\text{Unit} = \text{N·m}")

    def test_parse_grounded_response_turns_literal_newlines_into_real_breaks(self):
        parsed = parse_grounded_response(
            '{"textbook_answer":"প্রধান ধারণা\\\\n\\\\n- প্রথম পয়েন্ট","extra_explanation":"আরও\\\\nসহজভাবে"}'
        )

        self.assertEqual(parsed["textbook_answer"], "প্রধান ধারণা\n\n- প্রথম পয়েন্ট")
        self.assertEqual(parsed["extra_explanation"], "আরও\nসহজভাবে")


if __name__ == "__main__":
    unittest.main()
