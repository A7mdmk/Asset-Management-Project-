
from django.test import SimpleTestCase

from .ai_evaluation import evaluate_recommendations


class AIRecommendationEvaluationTests(SimpleTestCase):

    def test_perfect_recommendations(self):
        result = evaluate_recommendations(
            recommended_ids=["A", "B", "C"],
            relevant_ids=["A", "B", "C"],
        )

        self.assertEqual(result["precision_at_3"], 1.0)
        self.assertEqual(result["recall_at_3"], 1.0)
        self.assertEqual(result["relevant_recommendations"], 3)

    def test_partially_relevant_recommendations(self):
        result = evaluate_recommendations(
            recommended_ids=["A", "X", "B"],
            relevant_ids=["A", "B", "C"],
        )

        self.assertEqual(result["precision_at_3"], 0.6667)
        self.assertEqual(result["recall_at_3"], 0.6667)
        self.assertEqual(result["relevant_recommendations"], 2)

    def test_no_relevant_recommendations(self):
        result = evaluate_recommendations(
            recommended_ids=["X", "Y", "Z"],
            relevant_ids=["A", "B", "C"],
        )

        self.assertEqual(result["precision_at_3"], 0.0)
        self.assertEqual(result["recall_at_3"], 0.0)

    def test_duplicate_recommendations_count_once(self):
        result = evaluate_recommendations(
            recommended_ids=["A", "A", "B"],
            relevant_ids=["A", "B"],
        )

        self.assertEqual(result["total_recommended"], 2)
        self.assertEqual(result["relevant_recommendations"], 2)
        self.assertEqual(result["precision_at_3"], 0.6667)
        self.assertEqual(result["recall_at_3"], 1.0)

    def test_only_first_three_unique_recommendations_count(self):
        result = evaluate_recommendations(
            recommended_ids=["X", "Y", "Z", "A"],
            relevant_ids=["A"],
        )

        self.assertEqual(result["total_recommended"], 3)
        self.assertEqual(result["relevant_recommendations"], 0)
        self.assertEqual(result["precision_at_3"], 0.0)
        self.assertEqual(result["recall_at_3"], 0.0)

    def test_empty_recommendations(self):
        result = evaluate_recommendations(
            recommended_ids=[],
            relevant_ids=["A", "B"],
        )

        self.assertEqual(result["total_recommended"], 0)
        self.assertEqual(result["precision_at_3"], 0.0)
        self.assertEqual(result["recall_at_3"], 0.0)

    def test_empty_relevant_set(self):
        result = evaluate_recommendations(
            recommended_ids=["A", "B"],
            relevant_ids=[],
        )

        self.assertEqual(result["total_relevant"], 0)
        self.assertEqual(result["precision_at_3"], 0.0)
        self.assertEqual(result["recall_at_3"], 0.0)

    def test_invalid_recommendation_input(self):
        for invalid_input in (
            None,
            "A",
            123,
            {"A": 1},
        ):
            with self.subTest(value=repr(invalid_input)):
                with self.assertRaises(ValueError):
                    evaluate_recommendations(
                        recommended_ids=invalid_input,
                        relevant_ids=["A"],
                    )
