import importlib
import json
import os
import sys
import types
import unittest
from unittest.mock import patch


os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/photon_test")

try:
    import langchain_core.messages  # noqa: F401
except ModuleNotFoundError:
    langchain_core_module = types.ModuleType("langchain_core")
    langchain_core_messages = types.ModuleType("langchain_core.messages")
    langchain_core_tools = types.ModuleType("langchain_core.tools")

    class _BaseMessage:
        def __init__(self, content=None, **kwargs):
            del kwargs
            self.content = content

    def _tool(_name):
        def decorator(fn):
            return fn

        return decorator

    langchain_core_messages.AIMessage = _BaseMessage
    langchain_core_messages.HumanMessage = _BaseMessage
    langchain_core_messages.SystemMessage = _BaseMessage
    langchain_core_tools.tool = _tool
    langchain_core_module.messages = langchain_core_messages
    langchain_core_module.tools = langchain_core_tools

    sys.modules["langchain_core"] = langchain_core_module
    sys.modules["langchain_core.messages"] = langchain_core_messages
    sys.modules["langchain_core.tools"] = langchain_core_tools

from graph.exam_generator import (
    build_exam_batches,
    build_exam_prompt,
    distribute_questions_across_topics,
    generate_exam,
    parse_questions_payload,
    resolve_exam_max_tokens,
)

fastapi_main = importlib.import_module("main")


class ExamPipelineTests(unittest.TestCase):
    def setUp(self):
        fastapi_main._load_chapter_source_cached.cache_clear()
        fastapi_main._load_lesson_cached.cache_clear()

    def test_load_selected_exam_topics_accepts_topics_without_content(self):
        items = [
            {
                "content": {
                    "chapter_name": "Static Electricity",
                    "lessons": [
                        {
                            "lesson_name": "তড়িৎ বলরেখা",
                        }
                    ],
                }
            }
        ]

        with patch.object(fastapi_main, "get_main_items", return_value=items):
            selected_topics = fastapi_main.load_selected_exam_topics(
                [
                    {
                        "chapterName": "Static Electricity",
                        "topicNames": ["তড়িৎ বলরেখা"],
                    }
                ]
            )

        self.assertEqual(
            selected_topics,
            [
                {
                    "chapter_name": "Static Electricity",
                    "topic_name": "তড়িৎ বলরেখা",
                }
            ],
        )

    def test_build_exam_prompt_uses_topic_names_without_lesson_content(self):
        prompt = build_exam_prompt(
            [
                {
                    "chapter_name": "Static Electricity",
                    "topic_name": "তড়িৎ ক্ষেত্র",
                    "content": "SECRET LESSON CONTENT",
                }
            ],
            7,
        )

        self.assertIn("You are a Bangladeshi HSC physics tutor. Your job is to create a quiz.", prompt)
        self.assertIn("Number of questions: 7", prompt)
        self.assertIn("Static Electricity", prompt)
        self.assertIn("তড়িৎ ক্ষেত্র", prompt)
        self.assertNotIn("SECRET LESSON CONTENT", prompt)
        self.assertNotIn("Lesson context", prompt)

    def test_parse_questions_payload_rejects_unknown_selected_topic_pair(self):
        raw_output = json.dumps(
            {
                "questions": [
                    {
                        "chapter_name": "Static Electricity",
                        "topic_name": "আধান",
                        "question": "What is charge?",
                        "options": ["A", "B", "C", "D"],
                        "correct_option_index": 0,
                    }
                ]
            },
            ensure_ascii=False,
        )

        with self.assertRaisesRegex(ValueError, "unknown selected topic pair"):
            parse_questions_payload(
                raw_output,
                [
                    {
                        "chapter_name": "Static Electricity",
                        "topic_name": "তড়িৎ ক্ষেত্র",
                    }
                ],
                1,
            )

    def test_generate_exam_reports_provider_specific_missing_key_messages(self):
        selected_topics = [
            {
                "chapter_name": "Static Electricity",
                "topic_name": "তড়িৎ ক্ষেত্র",
            }
        ]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GROQ_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not set"):
                generate_exam(selected_topics, 1, selected_model="openai:gpt-5.4-nano")

            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY is not set"):
                generate_exam(selected_topics, 1, selected_model="groq:openai/gpt-oss-120b")

    def test_resolve_exam_max_tokens_scales_with_question_count(self):
        self.assertEqual(resolve_exam_max_tokens(1), 4096)
        self.assertEqual(resolve_exam_max_tokens(20), 10000)
        self.assertEqual(resolve_exam_max_tokens(50), 16000)

    def test_distribute_questions_across_topics_spreads_evenly(self):
        allocations = distribute_questions_across_topics(
            [
                {"chapter_name": "Static Electricity", "topic_name": "আধান"},
                {"chapter_name": "Static Electricity", "topic_name": "কুলম্বের সূত্র"},
                {"chapter_name": "Static Electricity", "topic_name": "তড়িৎ ক্ষেত্র"},
            ],
            8,
        )

        self.assertEqual([item["question_count"] for item in allocations], [3, 3, 2])

    def test_build_exam_batches_splits_large_generation_into_small_calls(self):
        batches = build_exam_batches(
            [
                {"chapter_name": "Static Electricity", "topic_name": "আধান"},
                {"chapter_name": "Static Electricity", "topic_name": "কুলম্বের সূত্র"},
            ],
            12,
        )

        self.assertEqual(sum(batch["question_count"] for batch in batches), 12)
        self.assertTrue(all(batch["question_count"] <= 5 for batch in batches))

    @patch("graph.exam_generator.invoke_llm_with_logging")
    @patch("graph.exam_generator.get_exam_llm")
    def test_generate_exam_surfaces_length_limit_as_clear_error(self, mock_get_exam_llm, mock_invoke):
        mock_get_exam_llm.return_value = object()
        mock_invoke.return_value = type(
            "FakeResponse",
            (),
            {
                "content": '{"questions": [{"chapter_name": "Static Electricity"',
                "response_metadata": {"finish_reason": "length"},
            },
        )()

        with self.assertRaisesRegex(ValueError, "cut off before finishing the exam JSON"):
            generate_exam(
                [
                    {
                        "chapter_name": "Static Electricity",
                        "topic_name": "তড়িৎ ক্ষেত্র",
                    }
                ],
                20,
            )

    @patch("graph.exam_generator.generate_exam_batch")
    def test_generate_exam_combines_batches_into_total_question_count(self, mock_generate_batch):
        mock_generate_batch.side_effect = [
            [
                {
                    "id": "q1",
                    "chapterName": "Static Electricity",
                    "topicName": "আধান",
                    "question": "Q1",
                    "options": ["A", "B", "C", "D"],
                    "correctOptionIndex": 0,
                },
                {
                    "id": "q2",
                    "chapterName": "Static Electricity",
                    "topicName": "আধান",
                    "question": "Q2",
                    "options": ["A", "B", "C", "D"],
                    "correctOptionIndex": 0,
                },
                {
                    "id": "q3",
                    "chapterName": "Static Electricity",
                    "topicName": "আধান",
                    "question": "Q3",
                    "options": ["A", "B", "C", "D"],
                    "correctOptionIndex": 0,
                },
            ],
            [
                {
                    "id": "q4",
                    "chapterName": "Static Electricity",
                    "topicName": "কুলম্বের সূত্র",
                    "question": "Q4",
                    "options": ["A", "B", "C", "D"],
                    "correctOptionIndex": 0,
                },
                {
                    "id": "q5",
                    "chapterName": "Static Electricity",
                    "topicName": "কুলম্বের সূত্র",
                    "question": "Q5",
                    "options": ["A", "B", "C", "D"],
                    "correctOptionIndex": 0,
                },
            ],
        ]

        questions = generate_exam(
            [
                {"chapter_name": "Static Electricity", "topic_name": "আধান"},
                {"chapter_name": "Static Electricity", "topic_name": "কুলম্বের সূত্র"},
            ],
            5,
        )

        self.assertEqual(len(questions), 5)
        self.assertEqual(
            [question["topicName"] for question in questions],
            ["আধান", "কুলম্বের সূত্র", "আধান", "কুলম্বের সূত্র", "আধান"],
        )


if __name__ == "__main__":
    unittest.main()
