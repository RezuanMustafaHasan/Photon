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

from graph.simple_graph import (
    AIMessage,
    HumanMessage,
    advance_topic,
    build_checkpoint_indexes,
    collect_turn_response_text,
    compose_chat_markdown,
    is_done_response,
    normalize_lesson_topics,
    parse_grounded_response,
    resolve_chat_model_config,
    resolve_images_for_response,
    route_after_teach,
    run_chat,
    should_advance_to_next_chunk,
    teach,
)


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return type("FakeResponse", (), {"content": self.content})()


class StatefulTutorLLM:
    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        system = getattr(messages[0], "content", "") if messages else ""
        user_prompt = getattr(messages[1], "content", "") if len(messages) > 1 else ""

        if "Plan the next micro-step" in system:
            if '"title": "A"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"next_focus":"A এর প্রথম ধারণা","remaining_after_this_reply":"A topic এর বাকি অংশ","topic_complete_after_reply":false,"ask_checkpoint_now":false}'},
                )()
            if '"title": "B"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"next_focus":"B এর শুরু","remaining_after_this_reply":"B topic এর বাকি অংশ","topic_complete_after_reply":false,"ask_checkpoint_now":false}'},
                )()
            return type(
                "FakeResponse",
                (),
                {"content": '{"next_focus":"পরের ছোট ধারণা","remaining_after_this_reply":"আরও আছে","topic_complete_after_reply":false,"ask_checkpoint_now":false}'},
            )()

        if "Update the running tutoring summary" in system:
            if '"title": "A"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"taught_concepts":["A এর প্রথম ধারণা"],"understood":[],"confusion":[],"next_to_teach":"A এর বাকি অংশ"}'},
                )()
            if '"title": "B"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"taught_concepts":["B এর শুরু"],"understood":[],"confusion":[],"next_to_teach":"B এর পরের অংশ"}'},
                )()
            return type(
                "FakeResponse",
                (),
                {"content": '{"taught_concepts":["একটি ছোট ধারণা"],"understood":[],"confusion":[],"next_to_teach":"পরের অংশ"}'},
            )()

        if "Topic 1 of 2: A" in system:
            return AIMessage("A topic এর শুধু প্রথম ছোট ধারণাটা বোঝাই।")
        if "Topic 2 of 2: B" in system:
            return AIMessage("B topic এর প্রথম ছোট ধারণাটা বোঝাই।")
        if "Topic 1 of 3: A" in system:
            return AIMessage("A topic শেষ করলাম।")
        if "Topic 2 of 3: B" in system:
            return AIMessage("এখন B topic এর প্রথম ছোট অংশ বোঝাই।")
        return AIMessage("একটা ছোট অংশ বোঝাই।")


class TopicAdvanceTutorLLM:
    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        system = getattr(messages[0], "content", "") if messages else ""
        user_prompt = getattr(messages[1], "content", "") if len(messages) > 1 else ""

        if "Plan the next micro-step" in system:
            if '"title": "A"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"next_focus":"A topic এর শেষ ছোট অংশ","remaining_after_this_reply":"nothing","topic_complete_after_reply":true,"ask_checkpoint_now":false}'},
                )()
            if '"title": "B"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"next_focus":"B topic এর প্রথম ছোট অংশ","remaining_after_this_reply":"B topic এর বাকি অংশ","topic_complete_after_reply":false,"ask_checkpoint_now":false}'},
                )()
            return type(
                "FakeResponse",
                (),
                {"content": '{"next_focus":"একটি ছোট অংশ","remaining_after_this_reply":"আরও আছে","topic_complete_after_reply":false,"ask_checkpoint_now":false}'},
            )()

        if "Update the running tutoring summary" in system:
            if '"title": "A"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"taught_concepts":["A topic"],"understood":[],"confusion":[],"next_to_teach":"B"}'},
                )()
            if '"title": "B"' in user_prompt:
                return type(
                    "FakeResponse",
                    (),
                    {"content": '{"taught_concepts":["B topic"],"understood":[],"confusion":[],"next_to_teach":"B topic এর বাকি অংশ"}'},
                )()
            return type(
                "FakeResponse",
                (),
                {"content": '{"taught_concepts":["একটি ধারণা"],"understood":[],"confusion":[],"next_to_teach":"পরের অংশ"}'},
            )()

        if "Topic 1 of 3: A" in system:
            return AIMessage("A topic শেষ করলাম।")
        if "Topic 2 of 3: B" in system:
            return AIMessage("এখন B topic এর প্রথম ছোট অংশ বোঝাই।")
        return AIMessage("একটা ছোট অংশ বোঝাই।")


STATEFUL_LESSON = {
    "lesson_name": "Coulomb's Law",
    "topics": [
        {
            "title": "মূল ধারণা",
            "content": "দুটি চার্জের মধ্যে বল দূরত্বের বর্গের ব্যস্তানুপাতিক।",
        },
        {
            "title": "সূত্র",
            "content": "কুলম্বের সূত্রের গাণিতিক রূপ $F = kq_1q_2 / r^2$।",
        },
    ],
}

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
    def test_normalize_lesson_topics_keeps_each_topic_atomic(self):
        topics = normalize_lesson_topics(STATEFUL_LESSON)

        self.assertEqual(len(topics), 2)
        self.assertEqual(topics[0]["title"], "মূল ধারণা")
        self.assertIn("কুলম্বের সূত্র", topics[1]["content"])

    def test_normalize_lesson_topics_falls_back_to_single_topic_without_chunking(self):
        topics = normalize_lesson_topics(
            {
                "lesson_name": "Electric Potential",
                "content": "পুরো lesson content এখানে একসাথে আছে।",
            }
        )

        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]["title"], "Electric Potential")
        self.assertEqual(topics[0]["content"], "পুরো lesson content এখানে একসাথে আছে।")

    def test_done_response_uses_uppercase_done_token(self):
        self.assertTrue(is_done_response(AIMessage("DONE")))
        self.assertTrue(is_done_response(AIMessage("Done")))
        self.assertFalse(is_done_response(AIMessage("DONE now")))

    def test_checkpoint_schedule_is_not_every_topic_for_medium_lesson(self):
        self.assertEqual(build_checkpoint_indexes(4), [1, 3])

    def test_should_advance_forces_move_after_max_turns_on_topic(self):
        state = {
            "lesson_complete": False,
            "awaiting_reply": True,
            "messages": [HumanMessage("আমি পুরোপুরি বুঝিনি")],
            "current_topic_turns": 4,
            "current_topic_index": 1,
            "checkpoint_indexes": [1, 3],
            "topics": STATEFUL_LESSON["topics"],
        }

        self.assertTrue(should_advance_to_next_chunk(state))

    def test_advance_topic_moves_topic_index_forward(self):
        state = {
            "lesson_complete": False,
            "current_topic_index": 0,
            "current_topic_turns": 1,
            "current_topic": STATEFUL_LESSON["topics"][0],
            "topics": STATEFUL_LESSON["topics"],
            "lesson_summary": {"next_to_teach": "মূল ধারণা"},
        }

        updated = advance_topic(state)

        self.assertEqual(updated["current_topic_index"], 1)
        self.assertEqual(updated["current_topic_turns"], 0)
        self.assertEqual(updated["current_topic"]["title"], "সূত্র")

    def test_collect_turn_response_text_joins_teaching_and_drops_done(self):
        text = collect_turn_response_text(
            [
                AIMessage("প্রথম topic বোঝাই।"),
                AIMessage("দ্বিতীয় topic-ও বুঝে নেই।"),
                AIMessage("DONE"),
            ]
        )

        self.assertIn("প্রথম topic", text)
        self.assertIn("দ্বিতীয় topic", text)
        self.assertNotEqual(text, "DONE")

    @patch("graph.simple_graph.get_llm")
    def test_teach_stops_after_one_small_reply(self, mock_get_llm):
        mock_get_llm.return_value = StatefulTutorLLM()

        state = {
            "chapter_name": "Static Electricity",
            "lesson_name": "Small Lesson",
            "chat_model": "groq:test-model",
            "topics": [
                {"title": "A", "content": "A topic content with multiple concepts."},
                {"title": "B", "content": "B topic content with multiple concepts."},
            ],
            "current_topic_index": 0,
            "current_topic_turns": 0,
            "current_topic": {"title": "A", "content": "A topic content with multiple concepts."},
            "topic_complete": False,
            "pending_action": "",
            "checkpoint_indexes": [1],
            "used_image_ids": [],
            "lesson_summary": {},
            "awaiting_reply": False,
            "lesson_complete": False,
            "messages": [HumanMessage("শুরু করো")],
        }

        result = teach(state)
        merged_state = {
            **state,
            **result,
            "messages": [*state["messages"], *(result.get("messages") or [])],
        }

        self.assertEqual(result["messages"][0].content, "A topic এর শুধু প্রথম ছোট ধারণাটা বোঝাই।")
        self.assertTrue(result["awaiting_reply"])
        self.assertFalse(result["topic_complete"])
        self.assertEqual(route_after_teach(merged_state), "end")

    def test_teach_marks_advance_pending_after_topic_completion(self):
        state = {
            "chapter_name": "Static Electricity",
            "lesson_name": "Progressive Lesson",
            "chat_model": "groq:test-model",
            "topics": [
                {"title": "A", "content": "A topic content."},
                {"title": "B", "content": "B topic content."},
                {"title": "C", "content": "C topic content."},
            ],
            "current_topic_index": 0,
            "current_topic_turns": 1,
            "current_topic": {"title": "A", "content": "A topic content."},
            "topic_complete": True,
            "pending_action": "",
            "checkpoint_indexes": [1, 2],
            "used_image_ids": [],
            "lesson_summary": {},
            "awaiting_reply": True,
            "lesson_complete": False,
            "messages": [AIMessage("A topic শেষ করলাম।"), HumanMessage("চলো সামনে যাই")],
        }

        result = teach(state)
        merged_state = {**state, **result}
        advanced = advance_topic(merged_state)

        self.assertEqual(result["pending_action"], "advance_topic")
        self.assertEqual(route_after_teach(merged_state), "advance_topic")
        self.assertEqual(advanced["current_topic_index"], 1)
        self.assertEqual(advanced["current_topic"]["title"], "B")

    @patch("graph.simple_graph.load_images_from_database")
    def test_resolve_images_returns_catalog_metadata(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-1",
                "imageURL": "https://example.com/potential.png",
                "description": "Two charged points and their separation",
                "topic": ["তড়িৎ বিভব"],
            }
        ]

        resolved = resolve_images_for_response(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বিভব",
            selected_images=[{"image_id": "img-1", "imageURL": "", "description": "", "topic": []}],
        )

        self.assertEqual(resolved[0]["image_id"], "img-1")
        self.assertEqual(resolved[0]["imageURL"], "https://example.com/potential.png")
        self.assertEqual(resolved[0]["description"], "Two charged points and their separation")

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

    @patch("graph.simple_graph.get_llm")
    def test_run_chat_passes_selected_chat_model_to_llm(self, mock_get_llm):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"পাঠ থেকে নেওয়া উত্তর।","extra_explanation":"অতিরিক্ত ব্যাখ্যা।"}'
        )

        run_chat(
            "thread-4",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [],
            "বল কমে কেন?",
            chat_model="openai:gpt-4.1-mini",
        )

        mock_get_llm.assert_called_with("openai:gpt-4.1-mini")

    def test_resolve_chat_model_config_accepts_provider_prefixed_models(self):
        config = resolve_chat_model_config("openai:gpt-5.4-nano")

        self.assertEqual(config["id"], "openai:gpt-5.4-nano")
        self.assertEqual(config["provider"], "openai")
        self.assertEqual(config["model"], "gpt-5.4-nano")

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
