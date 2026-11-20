
import json
from statistics import mean
from unittest.mock import patch

from .ai_benchmark_data import (
    BENCHMARK_ASSETS,
    BENCHMARK_CASES,
)
from .ai_evaluation import evaluate_recommendations
from .ai_recommendations import recommend_assets


def run_benchmark():
    """
    Evaluate actual Gemini recommendations against
    labelled synthetic benchmark cases.

    No production database records are changed.
    """

    print("\nKU ResourceSavers - AI Evaluation")
    print("=" * 50)

    results = []
    failures = []

    for index, case in enumerate(BENCHMARK_CASES, start=1):
        print(f"\nScenario {index}: {case['need']}")

        try:
            # Substitute the synthetic inventory.
            # Gemini itself is NOT mocked.
            with patch(
                "workflows.ai_recommendations.get_available_assets",
                return_value=BENCHMARK_ASSETS,
            ):
                response = recommend_assets(case["need"])

            recommended_ids = [
                asset["id"]
                for asset in response["recommendations"]
            ]

            metrics = evaluate_recommendations(
                recommended_ids=recommended_ids,
                relevant_ids=case["relevant_ids"],
            )

            print("Recommended:", recommended_ids)

            print("Recommendation explanations:")

            for asset in response["recommendations"]:
                print(
                    f"  {asset['name']}: "
                    f"{asset.get('explanation', 'No explanation')}"
                )

            print("Expected:", case["relevant_ids"])
            print(
                "Precision@3:",
                metrics["precision_at_3"],
            )
            print(
                "Recall@3:",
                metrics["recall_at_3"],
            )

            results.append({
                "scenario": case["need"],
                "recommended_ids": recommended_ids,
                "relevant_ids": case["relevant_ids"],
                **metrics,
            })

        except Exception as error:
            # Keep failed API calls separate from scored results.
            print(
                "Evaluation failed:",
                type(error).__name__,
                str(error),
            )

            failures.append({
                "scenario": case["need"],
                "error_type": type(error).__name__,
            })

    print("\n" + "=" * 50)
    print("FINAL BENCHMARK SUMMARY")

    total_cases = len(BENCHMARK_CASES)

    summary = {
        "total_cases": total_cases,
        "successful_cases": len(results),
        "failed_cases": len(failures),
        "average_precision_at_3": (
            round(
                mean(r["precision_at_3"] for r in results),
                4,
            )
            if results else None
        ),
        "average_recall_at_3": (
            round(
                mean(r["recall_at_3"] for r in results),
                4,
            )
            if results else None
        ),
    }

    print(json.dumps(summary, indent=2))

    if failures:
        print(
            "\nWarning: Failed scenarios were excluded "
            "from the averages."
        )

    if not results:
        print(
            "\nNo valid AI responses were evaluated. "
            "Check Gemini configuration and API access."
        )

    return {
        "summary": summary,
        "results": results,
        "failures": failures,
    }
