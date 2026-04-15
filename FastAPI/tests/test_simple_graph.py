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
    advance_turn,
    build_image_candidates_for_reply,
    build_checkpoint_indexes,
    build_lesson_image_plan,
    build_topic_plan,
    compose_chat_markdown,
    ensure_topic_transition,
    is_checkpoint_chunk,
    is_done_response,
    parse_grounded_response,
    resolve_chat_model_config,
    resolve_images_for_response,
    run_chat,
    should_advance_to_next_chunk,
)


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
    def test_build_topic_plan_keeps_one_topic_per_chunk(self):
        chunks = [
            "প্রথম topic এ electric potential এর প্রাথমিক ধারণা আছে।",
            "দ্বিতীয় topic এ potential difference ব্যাখ্যা করা হয়েছে।",
            "তৃতীয় topic এ কাজের সাথে সম্পর্ক দেখানো হয়েছে।",
        ]

        topic_plan = build_topic_plan(chunks)

        self.assertEqual(len(topic_plan), 3)
        self.assertIn("প্রথম topic", topic_plan[0])
        self.assertIn("দ্বিতীয় topic", topic_plan[1])

    def test_done_response_uses_uppercase_done_token(self):
        self.assertTrue(is_done_response(AIMessage("DONE")))
        self.assertTrue(is_done_response(AIMessage("Done")))
        self.assertFalse(is_done_response(AIMessage("DONE now")))

    def test_checkpoint_schedule_is_not_every_chunk_for_medium_lesson(self):
        lesson_chunks = ["topic 1", "topic 2", "topic 3", "topic 4"]

        self.assertFalse(is_checkpoint_chunk(0, lesson_chunks))
        self.assertTrue(is_checkpoint_chunk(1, lesson_chunks))
        self.assertFalse(is_checkpoint_chunk(2, lesson_chunks))
        self.assertTrue(is_checkpoint_chunk(3, lesson_chunks))
        self.assertEqual(build_checkpoint_indexes(len(lesson_chunks)), [1, 3])

    def test_should_advance_forces_move_after_max_turns_on_topic(self):
        state = {
            "lesson_complete": False,
            "awaiting_student_reply": True,
            "messages": [HumanMessage("আমি পুরোপুরি বুঝিনি")],
            "current_topic_turns": 2,
            "current_topic_index": 1,
            "checkpoint_indexes": [1, 3],
            "topic_plan": ["t1", "t2", "t3", "t4"],
            "lesson_chunks": ["c1", "c2", "c3", "c4"],
        }

        self.assertTrue(should_advance_to_next_chunk(state))

    def test_advance_turn_moves_topic_index_forward(self):
        state = {
            "lesson_complete": False,
            "awaiting_student_reply": True,
            "messages": [HumanMessage("next")],
            "current_topic_turns": 1,
            "current_chunk_turns": 1,
            "current_topic_index": 0,
            "current_chunk_index": 0,
            "checkpoint_indexes": [1],
            "topic_plan": ["topic 1", "topic 2"],
            "lesson_chunks": ["chunk 1", "chunk 2"],
            "lesson_summary": {"next_to_teach": "topic 1"},
        }

        updated = advance_turn(state)

        self.assertEqual(updated["current_topic_index"], 1)
        self.assertEqual(updated["current_topic_turns"], 0)
        self.assertEqual(updated["current_chunk_index"], 1)

    def test_ensure_topic_transition_prepends_intro_and_bridge(self):
        intro_state = {
            "lesson_name": "তড়িৎ বিভব",
            "topic_plan": ["মূল ধারণা", "বিভব পার্থক্য"],
            "current_topic_index": 0,
            "current_topic_turns": 0,
        }
        bridge_state = {
            "lesson_name": "তড়িৎ বিভব",
            "topic_plan": ["মূল ধারণা", "বিভব পার্থক্য"],
            "current_topic_index": 1,
            "current_topic_turns": 0,
        }

        intro_text = ensure_topic_transition("এখানে বিভবের মূল ধারণা বোঝানো হচ্ছে।", intro_state)
        bridge_text = ensure_topic_transition("এখন বিভব পার্থক্য বোঝাই।", bridge_state)

        self.assertIn("lesson", intro_text.lower())
        self.assertNotEqual(bridge_text, "এখন বিভব পার্থক্য বোঝাই।")

    def test_build_lesson_image_plan_assigns_images_to_matching_topics(self):
        lesson_chunks = [
            "তড়িৎ বিভবের ধারণা এবং দুটি বিন্দুর বিভব পার্থক্য।",
            "সমবিভব তল এবং তড়িৎ বলরেখার সঙ্গে এর সম্পর্ক।",
        ]
        images = [
            {
                "image_id": "img-potential",
                "imageURL": "https://example.com/potential.png",
                "description": "Two points with different electric potential",
                "topic": ["তড়িৎ বিভব"],
            },
            {
                "image_id": "img-equipotential",
                "imageURL": "https://example.com/equipotential.png",
                "description": "Equipotential surface crossing electric field lines",
                "topic": ["সমবিভব তল"],
            },
        ]

        plan = build_lesson_image_plan(lesson_chunks, images)

        self.assertEqual(plan[0][0]["image_id"], "img-potential")
        self.assertEqual(plan[1][0]["image_id"], "img-equipotential")

    @patch("graph.simple_graph.load_images_from_database")
    def test_build_image_candidates_avoids_reusing_used_images(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-used",
                "imageURL": "https://example.com/used.png",
                "description": "Electric field lines around a positive charge",
                "topic": ["তড়িৎ বলরেখা"],
            },
            {
                "image_id": "img-fresh",
                "imageURL": "https://example.com/fresh.png",
                "description": "Electric field lines between two charges",
                "topic": ["তড়িৎ বলরেখা"],
            },
        ]

        candidates = build_image_candidates_for_reply(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বলরেখা",
            response_text="এখানে তড়িৎ বলরেখার দিক বোঝানো হচ্ছে।",
            user_text="ছবি দিয়ে বুঝাও",
            current_chunk="তড়িৎ বলরেখা ধনাত্মক চার্জ থেকে ঋণাত্মক চার্জের দিকে যায়।",
            topic_image_map={
                "0": [
                    {
                        "image_id": "img-fresh",
                        "description": "Electric field lines between two charges",
                        "topics": ["তড়িৎ বলরেখা"],
                    }
                ]
            },
            current_chunk_index=0,
            used_image_ids={"img-used"},
            tool_selected_images=[],
        )

        candidate_ids = [item["image_id"] for item in candidates]
        self.assertNotIn("img-used", candidate_ids)
        self.assertIn("img-fresh", candidate_ids)

    @patch("graph.simple_graph.load_images_from_database")
    def test_build_image_candidates_never_recycles_used_images(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-used",
                "imageURL": "https://example.com/used.png",
                "description": "Electric field lines around a positive charge",
                "topic": ["তড়িৎ বলরেখা"],
            }
        ]

        candidates = build_image_candidates_for_reply(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বলরেখা",
            response_text="এখানে তড়িৎ বলরেখার দিক বোঝানো হচ্ছে।",
            user_text="ছবি দিয়ে বুঝাও",
            current_chunk="তড়িৎ বলরেখা ধনাত্মক চার্জ থেকে ঋণাত্মক চার্জের দিকে যায়।",
            topic_image_map={},
            current_chunk_index=0,
            used_image_ids={"img-used"},
            tool_selected_images=[],
        )

        self.assertEqual(candidates, [])

    @patch("graph.simple_graph.call_llm_for_json")
    @patch("graph.simple_graph.load_images_from_database")
    def test_resolve_images_rewrites_database_caption_for_display(self, mock_load_images, mock_call_llm_for_json):
        mock_load_images.return_value = [
            {
                "image_id": "img-1",
                "imageURL": "https://example.com/potential.png",
                "description": "Raw database description of two charged points",
                "topic": ["তড়িৎ বিভব"],
            }
        ]
        mock_call_llm_for_json.return_value = {
            "images": [
                {
                    "image_id": "img-1",
                    "description": "এখানে দুটি বিন্দুর বিভবের তুলনা দেখানো হয়েছে।",
                }
            ]
        }

        resolved = resolve_images_for_response(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বিভব",
            selected_images=[{"image_id": "img-1", "description": "", "topics": ["তড়িৎ বিভব"]}],
            response_text="এই ছবিতে দুই বিন্দুর বিভবের পার্থক্য বোঝা যাবে।",
            current_chunk="দুটি বিন্দুর বিভব পার্থক্য কাজের ধারণার সঙ্গে সম্পর্কিত।",
        )

        self.assertEqual(resolved[0]["image_id"], "img-1")
        self.assertEqual(resolved[0]["description"], "এখানে দুটি বিন্দুর বিভবের তুলনা দেখানো হয়েছে।")
        self.assertNotEqual(
            resolved[0]["description"],
            "Raw database description of two charged points",
        )

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
