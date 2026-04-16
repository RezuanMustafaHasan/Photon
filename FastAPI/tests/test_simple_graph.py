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
    build_retrieval_query,
    compose_chat_markdown,
    extract_figure_hints,
    find_best_lesson_image,
    parse_grounded_response,
    resolve_chat_model_config,
    resolve_images_for_response,
    run_chat,
    select_images_for_concept,
)


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return type("FakeResponse", (), {"content": self.content})()


class MultiStageLLM:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        system = getattr(messages[0], "content", "") if messages else ""
        if "Rewrite a lesson image caption" in system:
            return type(
                "FakeResponse",
                (),
                {"content": '{"description":"এই ছবিতে দুটি চার্জের মাঝে দূরত্ব ও বলের সম্পর্ক দেখানো হয়েছে।"}'},
            )()
        return type(
            "FakeResponse",
            (),
            {
                "content": '{"textbook_answer":"দূরত্ব বাড়লে বল কমে যায় কারণ এটি $r^2$ এর ব্যস্তানুপাতিক।","extra_explanation":"সহজভাবে বললে, দূরে গেলে চার্জের প্রভাব ছড়িয়ে পড়ে।"}'
            },
        )()


class LessonFlowLLM:
    def __init__(self, contents):
        self.contents = list(contents)
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        index = len(self.messages) - 1
        if index >= len(self.contents):
            index = len(self.contents) - 1
        return type("FakeResponse", (), {"content": self.contents[index]})()


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

TOPIC_LESSON = {
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

FLOW_TOPIC_LESSON = {
    "lesson_name": "Newton's Third Law",
    "topics": [
        {
            "title": "ধারণা ১",
            "content": "প্রতিটি ক্রিয়ার বিপরীতে একটি সমান ও বিপরীতমুখী প্রতিক্রিয়া থাকে।",
        },
        {
            "title": "ধারণা ২",
            "content": "ক্রিয়া ও প্রতিক্রিয়া বল দুটি ভিন্ন বস্তুর উপর কাজ করে।",
        },
        {
            "title": "ধারণা ৩",
            "content": "এই দুই বলের মান সমান হলেও দিক বিপরীত হয়।",
        },
        {
            "title": "ধারণা ৪",
            "content": "তাই তারা একে অন্যকে বাতিল করে না, কারণ তারা একই বস্তুর উপর কাজ করে না।",
        },
    ],
}

ONE_TOPIC_LESSON = {
    "lesson_name": "Simple Harmonic Motion",
    "topics": [
        {
            "title": "মূল ধারণা",
            "content": "সরল হার্মোনিক গতিতে পুনঃস্থাপন বল সবসময় সরণের বিপরীত দিকে কাজ করে।",
        }
    ],
}

FIGURE_TOPIC_LESSON = {
    "lesson_name": "তড়িৎ বলরেখা",
    "topics": [
        {
            "title": "২.৬ তড়িৎ বলরেখা",
            "content": (
                "তড়িৎ বলরেখা হলো তড়িৎক্ষেত্রকে বোঝানোর একটি কল্পিত উপায়।\n"
                "চিত্র ২.৬: বিভিন্ন আধানের ক্ষেত্রে তড়িৎ বলরেখার বিন্যাস\n"
                "ধনাত্মক আধান থেকে রেখা বের হয় এবং ঋণাত্মক আধানের দিকে যায়।"
            ),
        }
    ],
}


class SimpleGraphTests(unittest.TestCase):
    def test_compose_chat_markdown_returns_plain_step_text(self):
        output = compose_chat_markdown(
            "This comes from the lesson.",
            "This is extra intuition.",
            [
                {
                    "section_label": "Page 1 / Coulomb's Law",
                    "snippet": "Force is inversely proportional to r^2.",
                }
            ],
            check_question="What happens next?",
        )

        self.assertIn("This comes from the lesson.", output)
        self.assertIn("This is extra intuition.", output)
        self.assertIn("ছোট প্রশ্ন: What happens next?", output)
        self.assertNotIn("From your lesson", output)
        self.assertNotIn("Extra explanation", output)
        self.assertNotIn("Sources", output)

    def test_compose_chat_markdown_strips_diagram_serials(self):
        output = compose_chat_markdown(
            "চিত্র ২.৬: এই বিন্যাসে রেখার দিক বোঝানো হয়েছে।",
            "Figure 3.1 দেখালে আরও পরিষ্কার হয়।",
            [],
            check_question="চিত্র ১.২ অনুযায়ী দিক কী?",
        )

        self.assertNotIn("২.৬", output)
        self.assertNotIn("3.1", output)
        self.assertNotIn("১.২", output)

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

    def test_resolve_chat_model_config_accepts_provider_prefixed_models(self):
        config = resolve_chat_model_config("openai:gpt-5.4-nano")

        self.assertEqual(config["id"], "openai:gpt-5.4-nano")
        self.assertEqual(config["provider"], "openai")
        self.assertEqual(config["model"], "gpt-5.4-nano")

    def test_build_retrieval_query_keeps_start_intent_clean(self):
        query = build_retrieval_query(
            "start",
            [{"role": "assistant", "content": "Ask your question here."}],
        )

        self.assertEqual(query, "start")

    def test_extract_figure_hints_prefers_figure_titles(self):
        hints = extract_figure_hints(
            "তড়িৎ বলরেখা বোঝার জন্য চিত্র ২.৬: বিভিন্ন আধানের ক্ষেত্রে তড়িৎ বলরেখার বিন্যাস দেখা যায়।"
        )

        self.assertEqual(len(hints), 1)
        self.assertIn("তড়িৎ বলরেখার বিন্যাস", hints[0])

    @patch("graph.simple_graph.load_images_from_database")
    def test_find_best_lesson_image_matches_relevant_caption(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-field",
                "imageURL": "https://example.com/field.png",
                "description": "Electric field lines around a charge",
                "topic": ["তড়িৎ ক্ষেত্র"],
            },
            {
                "image_id": "img-coulomb",
                "imageURL": "https://example.com/coulomb.png",
                "description": "Two charges separated by distance r showing Coulomb force",
                "topic": ["কুলম্বের সূত্র"],
            },
        ]

        image = find_best_lesson_image(
            chapter_name="Static Electricity",
            lesson_name="Coulomb's Law",
            hint="distance r and Coulomb force between two charges",
        )

        self.assertIsNotNone(image)
        self.assertEqual(image["image_id"], "img-coulomb")

    @patch("graph.simple_graph.load_images_from_database")
    def test_select_images_for_concept_uses_figure_hint_from_topic_content(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-lines",
                "imageURL": "https://example.com/lines.png",
                "description": "বিভিন্ন আধানের ক্ষেত্রে তড়িৎ বলরেখার বিন্যাস",
                "topic": ["তড়িৎ বলরেখা"],
            },
            {
                "image_id": "img-other",
                "imageURL": "https://example.com/other.png",
                "description": "অপ্রাসঙ্গিক ছবি",
                "topic": ["অন্য বিষয়"],
            },
        ]

        selected = select_images_for_concept(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বলরেখা",
            concept={
                "section_label": "তড়িৎ বলরেখা",
                "chunk_text": FIGURE_TOPIC_LESSON["topics"][0]["content"],
            },
            response_text="",
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["image_id"], "img-lines")

    @patch("graph.simple_graph.load_images_from_database")
    def test_select_images_for_concept_falls_back_to_best_unused_relevant_image(self, mock_load_images):
        mock_load_images.return_value = [
            {
                "image_id": "img-potential",
                "imageURL": "https://example.com/potential.png",
                "description": "Electric potential difference between two charged conductors",
                "topic": ["তড়িৎ বিভব"],
            },
            {
                "image_id": "img-other",
                "imageURL": "https://example.com/other.png",
                "description": "অপ্রাসঙ্গিক ছবি",
                "topic": ["অন্য বিষয়"],
            },
        ]

        selected = select_images_for_concept(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বিভব",
            concept={
                "section_label": "তড়িৎ বিভব",
                "chunk_text": "দুটি পরিবাহীর বিভবের পার্থক্য আধান প্রবাহের দিক নির্ধারণ করে।",
            },
            response_text="### বিভব\n\nদুটি পরিবাহীর মধ্যে $V$ ভিন্ন হলে আধান চলাচল করে।",
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["image_id"], "img-potential")

    @patch("graph.simple_graph.get_llm")
    @patch("graph.simple_graph.load_images_from_database")
    def test_resolve_images_rewrites_database_caption_for_display(self, mock_load_images, mock_get_llm):
        mock_load_images.return_value = [
            {
                "image_id": "img-1",
                "imageURL": "https://example.com/potential.png",
                "description": "Raw database description of two charged points",
                "topic": ["তড়িৎ বিভব"],
            }
        ]
        mock_get_llm.return_value = FakeLLM(
            '{"description":"এই ছবিতে দুটি চার্জের অবস্থান আর দূরত্ব দেখানো হয়েছে।"}'
        )

        resolved = resolve_images_for_response(
            chapter_name="Static Electricity",
            lesson_name="তড়িৎ বিভব",
            selected_images=[{"image_id": "img-1", "imageURL": "", "description": "", "topic": ["তড়িৎ বিভব"]}],
            response_text="এই ছবিটি দেখলে দূরত্বের ধারণা আরও পরিষ্কার হবে।",
            chat_model="groq:test-model",
        )

        self.assertEqual(resolved[0]["image_id"], "img-1")
        self.assertEqual(resolved[0]["description"], "এই ছবিতে দুটি চার্জের অবস্থান আর দূরত্ব দেখানো হয়েছে।")
        self.assertNotEqual(resolved[0]["description"], "Raw database description of two charged points")

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_returns_structured_grounded_payload(self, mock_get_llm, _mock_load_images):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"দূরত্ব বাড়লে বল কমে যায় কারণ এটি $r^2$ এর ব্যস্তানুপাতিক।","extra_explanation":"সহজভাবে বললে, দূরে গেলে চার্জের প্রভাব ছড়িয়ে পড়ে।"}'
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
        self.assertEqual(result["images"], [])
        self.assertIn("দূরত্ব বাড়লে বল কমে যায়", result["response"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_treats_start_as_lesson_intro(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"আজ আমরা কুলম্বের সূত্রের মূল ধারণা শুরু করছি। এখানে দুটি চার্জের মধ্যকার বল দূরত্বের সঙ্গে কীভাবে বদলায়, সেটি বোঝানো হয়েছে।","extra_explanation":"সহজভাবে ভাবো, দূরত্ব বাড়লে প্রভাব ছড়িয়ে পড়ে বলে বল কমে যায়।","check_question":"দূরত্ব বাড়লে বলের মান কীভাবে বদলায়?"}'
            ]
        )
        mock_get_llm.return_value = llm

        result = run_chat(
            "thread-start",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [{"role": "assistant", "content": "Ask your question here."}],
            "start",
        )

        self.assertIn("কুলম্বের সূত্র", result["textbook_answer"])
        self.assertIn("ছোট প্রশ্ন:", result["response"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_start_enters_lesson_flow_and_asks_check_question(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"আজ আমরা নিউটনের তৃতীয় সূত্রের প্রথম ধারণা দেখছি। প্রতিটি ক্রিয়ার বিপরীতে সমান ও বিপরীতমুখী প্রতিক্রিয়া থাকে।","extra_explanation":"যেমন তুমি দেয়ালকে ঠেললে দেয়ালও তোমাকে সমান বল দেয়।","check_question":"ক্রিয়া ও প্রতিক্রিয়ার দিক কেমন হয়?"}'
            ]
        )
        mock_get_llm.return_value = llm

        result = run_chat(
            "flow-1",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [],
            "start",
        )

        self.assertIn("ছোট প্রশ্ন:", result["response"])
        self.assertEqual(result["check_question"], "ক্রিয়া ও প্রতিক্রিয়ার দিক কেমন হয়?")
        self.assertTrue(result["thread_state"]["awaiting_understanding"])
        self.assertEqual(result["thread_state"]["concept_index"], 0)
        self.assertEqual(result["thread_state"]["current_step_index"], 0)
        self.assertFalse(result["thread_state"]["lesson_complete"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_advances_to_next_concept_after_positive_reply(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"প্রথম ধারণা: প্রতিটি ক্রিয়ার বিপরীতে সমান ও বিপরীত প্রতিক্রিয়া থাকে।","extra_explanation":"এটি জোড়া বল হিসেবে কাজ করে।","check_question":"প্রতিক্রিয়া বল কি থাকে?"}',
                '{"textbook_answer":"এবার দ্বিতীয় ধারণা: ক্রিয়া ও প্রতিক্রিয়া দুটি ভিন্ন বস্তুর উপর কাজ করে।","extra_explanation":"তাই তারা একে অন্যকে বাতিল করে না।","check_question":"ক্রিয়া ও প্রতিক্রিয়া কি একই বস্তুর উপর কাজ করে?"}',
            ]
        )
        mock_get_llm.return_value = llm

        first = run_chat(
            "flow-2",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [],
            "start",
        )
        second = run_chat(
            "flow-2",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [{"role": "assistant", "content": first["response"]}],
            "fine",
            saved_thread_state=first["thread_state"],
        )

        self.assertIn("দ্বিতীয় ধারণা", second["textbook_answer"])
        self.assertIn("তোমার আগের উত্তর ঠিক আছে", second["response"])
        self.assertEqual(second["thread_state"]["concept_index"], 1)
        self.assertEqual(second["thread_state"]["current_step_index"], 1)
        self.assertTrue(second["thread_state"]["awaiting_understanding"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_answers_side_question_without_losing_lesson_step(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"প্রথম ধারণা: প্রতিটি ক্রিয়ার বিপরীতে সমান ও বিপরীত প্রতিক্রিয়া থাকে।","extra_explanation":"এটি জোড়া বল হিসেবে কাজ করে।","check_question":"প্রতিক্রিয়া বল কি থাকে?"}',
                '{"textbook_answer":"ভালো প্রশ্ন। সমান হয় কারণ ক্রিয়া-প্রতিক্রিয়া একই আন্তঃক্রিয়ার জোড়া বল।","extra_explanation":"একটি বস্তু অন্যটিতে যত বল দেয়, অন্যটিও তত বল ফিরিয়ে দেয়।","check_question":"এই জোড়া বল কি একই বস্তুর উপর কাজ করে?"}',
            ]
        )
        mock_get_llm.return_value = llm

        first = run_chat(
            "flow-side-q",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [],
            "start",
        )
        second = run_chat(
            "flow-side-q",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [{"role": "assistant", "content": first["response"]}],
            "কিন্তু সমান হয় কেন?",
            saved_thread_state=first["thread_state"],
        )

        self.assertIn("ভালো প্রশ্ন", second["textbook_answer"])
        self.assertEqual(second["thread_state"]["concept_index"], 0)
        self.assertEqual(second["thread_state"]["current_step_index"], 0)
        self.assertTrue(second["thread_state"]["awaiting_understanding"])
        self.assertIn("ছোট প্রশ্ন:", second["response"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_returns_done_after_last_concept_and_allows_follow_up_qa(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"আজ আমরা সরল হার্মোনিক গতির মূল ধারণা দেখছি। পুনঃস্থাপন বল সরণের বিপরীত দিকে থাকে।","extra_explanation":"এই কারণেই বস্তু ভারসাম্যের দিকে ফিরে আসে।","check_question":"পুনঃস্থাপন বল কোন দিকে কাজ করে?"}',
                '{"textbook_answer":"পুনঃস্থাপন বল সবসময় সরণের বিপরীত দিকে কাজ করে।","extra_explanation":"এটাই সরল হার্মোনিক গতির মূল শর্ত।"}',
            ]
        )
        mock_get_llm.return_value = llm

        first = run_chat(
            "flow-done",
            "Oscillation",
            "Simple Harmonic Motion",
            ONE_TOPIC_LESSON,
            [],
            "start",
        )
        done = run_chat(
            "flow-done",
            "Oscillation",
            "Simple Harmonic Motion",
            ONE_TOPIC_LESSON,
            [{"role": "assistant", "content": first["response"]}],
            "fine",
            saved_thread_state=first["thread_state"],
        )
        follow_up = run_chat(
            "flow-done",
            "Oscillation",
            "Simple Harmonic Motion",
            ONE_TOPIC_LESSON,
            [
                {"role": "assistant", "content": first["response"]},
                {"role": "assistant", "content": done["response"]},
            ],
            "এখন বলো, সরল হার্মোনিক গতি কী?",
            saved_thread_state=done["thread_state"],
        )

        self.assertEqual(done["response"], "DONE")
        self.assertEqual(done["textbook_answer"], "DONE")
        self.assertTrue(done["thread_state"]["lesson_complete"])
        self.assertFalse(done["thread_state"]["awaiting_understanding"])
        self.assertIn("সরল হার্মোনিক", follow_up["response"])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_advances_on_short_keyword_reply(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"### বিভব\\\\n\\\\nবিভব হলো আধানের তড়িৎগত অবস্থার পরিমাপ।","extra_explanation":"দুটি পরিবাহীর বিভব ভিন্ন হলে আধান চলাচল করে।","check_question":"আধানের আদান-প্রদান মূলত কিসের উপর নির্ভর করে?"}',
                '{"textbook_answer":"### বিভবের সমতা\\\\n\\\\nদুটি পরিবাহীর বিভব সমান হলে আধান চলাচল থেমে যায়।","extra_explanation":"","check_question":"বিভব সমান হলে আধান চলাচল কেন থামে?"}',
            ]
        )
        mock_get_llm.return_value = llm

        lesson = {
            "lesson_name": "তড়িৎ বিভব",
            "topics": [
                {"title": "বিভব", "content": "বিভব আধানের তড়িৎগত অবস্থার পরিমাপ।"},
                {"title": "বিভবের সমতা", "content": "বিভব সমান হলে আধান প্রবাহ থাকে না।"},
            ],
        }

        first = run_chat(
            "flow-kw",
            "Static Electricity",
            "তড়িৎ বিভব",
            lesson,
            [],
            "start",
        )
        second = run_chat(
            "flow-kw",
            "Static Electricity",
            "তড়িৎ বিভব",
            lesson,
            [{"role": "assistant", "content": first["response"]}],
            "bivob",
            saved_thread_state=first["thread_state"],
        )

        self.assertIn("বিভবের সমতা", second["textbook_answer"])
        self.assertEqual(second["thread_state"]["current_step_index"], 1)

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_reexplains_same_concept_when_student_is_not_clear(self, mock_get_llm, _mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"প্রথম ধারণা: প্রতিটি ক্রিয়ার বিপরীতে সমান ও বিপরীত প্রতিক্রিয়া থাকে।","extra_explanation":"এটি জোড়া বল।","check_question":"প্রতিক্রিয়া বলের দিক কেমন?"}',
                '{"textbook_answer":"আবার সহজভাবে বলি, তুমি যদি নৌকা থেকে তীরে লাফ দাও, নৌকা পেছনে সরে যায়। এটাই বিপরীত প্রতিক্রিয়া।","extra_explanation":"একটি বল সামনে, অন্যটি বিপরীত দিকে কাজ করে।","check_question":"তুমি নৌকা ঠেললে নৌকা কোন দিকে যাবে?"}',
            ]
        )
        mock_get_llm.return_value = llm

        first = run_chat(
            "flow-3",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [],
            "start",
        )
        second = run_chat(
            "flow-3",
            "Dynamics",
            "Newton's Third Law",
            FLOW_TOPIC_LESSON,
            [{"role": "assistant", "content": first["response"]}],
            "বুঝিনি",
            saved_thread_state=first["thread_state"],
        )

        self.assertIn("আবার সহজভাবে", second["textbook_answer"])
        self.assertIn("তোমার আগের উত্তর পুরোপুরি ঠিক হয়নি", second["response"])
        self.assertEqual(second["thread_state"]["concept_index"], 0)
        self.assertEqual(second["thread_state"]["current_step_index"], 0)
        self.assertTrue(second["thread_state"]["awaiting_understanding"])

    @patch("graph.simple_graph.load_images_from_database")
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_can_reuse_image_when_highly_relevant_in_lesson_flow(self, mock_get_llm, mock_load_images):
        llm = LessonFlowLLM(
            [
                '{"textbook_answer":"প্রথম ধাপ: তড়িৎ বলরেখা ধনাত্মক আধান থেকে বের হয়।","extra_explanation":"","check_question":"ধনাত্মক আধান থেকে রেখা কোন দিকে যায়?"}',
                '{"textbook_answer":"দ্বিতীয় ধাপ: ঋণাত্মক আধানের দিকে রেখা গিয়ে শেষ হয়।","extra_explanation":"","check_question":"ঋণাত্মক আধানের কাছে রেখাগুলো কী করে?"}',
            ]
        )
        mock_get_llm.return_value = llm
        mock_load_images.return_value = [
            {
                "image_id": "img-lines",
                "imageURL": "https://example.com/lines.png",
                "description": "বিভিন্ন আধানের ক্ষেত্রে তড়িৎ বলরেখার বিন্যাস",
                "topic": ["তড়িৎ বলরেখা"],
            }
        ]

        first = run_chat(
            "flow-img",
            "Static Electricity",
            "তড়িৎ বলরেখা",
            FIGURE_TOPIC_LESSON,
            [],
            "start",
        )
        second = run_chat(
            "flow-img",
            "Static Electricity",
            "তড়িৎ বলরেখা",
            {
                "lesson_name": "তড়িৎ বলরেখা",
                "topics": [
                    FIGURE_TOPIC_LESSON["topics"][0],
                    {
                        "title": "পরবর্তী অংশ",
                        "content": (
                            "তড়িৎ বলরেখা কখনো একে অন্যকে ছেদ করে না।\n"
                            "চিত্র ২.৭: বিভিন্ন আধানের ক্ষেত্রে তড়িৎ বলরেখার বিন্যাস\n"
                            "এই বিন্যাসে দেখা যায় রেখার দিক সবসময় নির্দিষ্ট।"
                        ),
                    },
                ],
            },
            [{"role": "assistant", "content": first["response"]}],
            "fine",
            saved_thread_state=first["thread_state"],
        )

        self.assertEqual(len(first["images"]), 1)
        self.assertEqual(first["images"][0]["image_id"], "img-lines")
        self.assertEqual(len(second["images"]), 1)
        self.assertEqual(second["images"][0]["image_id"], "img-lines")

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_supports_topic_structured_lesson_source(self, mock_get_llm, _mock_load_images):
        mock_get_llm.return_value = FakeLLM(
            '{"textbook_answer":"কুলম্বের সূত্রে বল দূরত্বের বর্গের ব্যস্তানুপাতিক।","extra_explanation":"এটি চার্জের প্রভাব ছড়িয়ে পড়ার একটি সহজ ধারণা দেয়।"}'
        )

        result = run_chat(
            "thread-structured",
            "Static Electricity",
            "Coulomb's Law",
            TOPIC_LESSON,
            [],
            "কুলম্বের সূত্র কী বলে?",
        )

        self.assertIn("কুলম্বের সূত্র", result["textbook_answer"])
        self.assertEqual(result["citations"], [])

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_allows_extra_section_for_outside_lesson_question(self, mock_get_llm, _mock_load_images):
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

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_adds_source_only_for_cross_lesson_match(self, mock_get_llm, _mock_load_images):
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

    @patch("graph.simple_graph.load_images_from_database", return_value=[])
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_passes_selected_chat_model_to_llm(self, mock_get_llm, _mock_load_images):
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

    @patch("graph.simple_graph.load_images_from_database")
    @patch("graph.simple_graph.get_llm")
    def test_run_chat_attaches_relevant_image(self, mock_get_llm, mock_load_images):
        mock_get_llm.return_value = MultiStageLLM()
        mock_load_images.return_value = [
            {
                "image_id": "img-coulomb",
                "imageURL": "https://example.com/coulomb.png",
                "description": "Two charges separated by distance r showing Coulomb force",
                "topic": ["কুলম্বের সূত্র"],
            }
        ]

        result = run_chat(
            "thread-5",
            "Static Electricity",
            "Coulomb's Law",
            [SAMPLE_LESSON, SECOND_LESSON],
            [],
            "দূরত্ব বাড়লে বল কেন কমে যায়?",
        )

        self.assertEqual(len(result["images"]), 1)
        self.assertEqual(result["images"][0]["image_id"], "img-coulomb")
        self.assertIn("এই ছবিতে", result["images"][0]["description"])


if __name__ == "__main__":
    unittest.main()
