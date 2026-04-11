import unittest

from graph.lesson_grounding import (
    chunk_lesson_content,
    retrieve_relevant_chunks,
    retrieve_relevant_lesson_chunks,
)


SAMPLE_CONTENT = """
Page 1
## Coulomb's Law

চার্জ দুটি দূরে গেলে বল কমে যায়। বল দূরত্বের বর্গের ব্যস্তানুপাতিক।

### Formula

F = kq1q2 / r^2

Page 2
## Electric Field

তড়িৎ ক্ষেত্র হলো চার্জের চারপাশের সেই অঞ্চল যেখানে অন্য চার্জ বল অনুভব করে।
"""


class LessonGroundingTests(unittest.TestCase):
    def test_chunking_derives_stable_section_labels_and_snippets(self):
        chunks = chunk_lesson_content(SAMPLE_CONTENT, max_chars=140, max_paragraphs=1)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["section_label"], "Page 1 / Coulomb's Law")
        self.assertIn("দূরে গেলে বল কমে যায়", chunks[0]["snippet"])
        self.assertEqual(chunks[1]["section_label"], "Page 1 / Formula")

    def test_retrieval_matches_relevant_chunk_for_targeted_question(self):
        result = retrieve_relevant_chunks(
            SAMPLE_CONTENT,
            "দূরত্ব বাড়লে বল কেন কমে যায়?",
            top_k=2,
        )

        self.assertEqual(result["mode"], "matched")
        self.assertTrue(result["chunks"])
        self.assertIn("Coulomb", result["chunks"][0]["section_label"])

    def test_intro_queries_fall_back_to_the_opening_lesson_chunks(self):
        result = retrieve_relevant_chunks(
            SAMPLE_CONTENT,
            "start",
            top_k=2,
        )

        self.assertEqual(result["mode"], "intro")
        self.assertEqual(len(result["chunks"]), 2)
        self.assertEqual(result["chunks"][0]["section_label"], "Page 1 / Coulomb's Law")

    def test_cross_lesson_retrieval_picks_the_best_matching_lesson(self):
        catalog = [
            {
                "chapter_name": "Static Electricity",
                "lesson_name": "ধারকের শক্তি",
                "content": """
Page 1
## ধারকের শক্তি

ধারকের সঞ্চিত শক্তি $U = \\frac{Q^2}{2C}$।
""",
            },
            {
                "chapter_name": "Static Electricity",
                "lesson_name": "তড়িৎ বলরেখা",
                "content": """
Page 2
## তড়িৎ বলরেখা

তড়িৎ বলরেখা ধনাত্মক চার্জ থেকে ঋণাত্মক চার্জের দিকে যায়।
""",
            },
        ]

        result = retrieve_relevant_lesson_chunks(
            catalog,
            "বলরেখা কী?",
            current_lesson_name="ধারকের শক্তি",
            top_k=2,
        )

        self.assertEqual(result["mode"], "matched")
        self.assertEqual(result["source_lesson_name"], "তড়িৎ বলরেখা")
        self.assertTrue(result["chunks"])
        self.assertEqual(result["chunks"][0]["lesson_name"], "তড়িৎ বলরেখা")


if __name__ == "__main__":
    unittest.main()
