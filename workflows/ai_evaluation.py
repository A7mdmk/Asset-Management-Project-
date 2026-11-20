
def evaluate_recommendations(recommended_ids, relevant_ids):
    """
    Evaluate recommendation relevance using Precision@3
    and Recall@3.

    recommended_ids: ranked list of recommended asset IDs
    relevant_ids: collection of known relevant asset IDs
    """

    if not isinstance(recommended_ids, (list, tuple)):
        raise ValueError("Recommendations must be a list or tuple.")

    relevant = set(relevant_ids)

    # Evaluate the first three unique recommendations.
    top_three = list(dict.fromkeys(recommended_ids))[:3]

    relevant_recommendations = sum(
        1 for asset_id in top_three
        if asset_id in relevant
    )

    precision_at_3 = relevant_recommendations / 3

    recall_at_3 = (
        relevant_recommendations / len(relevant)
        if relevant
        else 0.0
    )

    return {
        "precision_at_3": round(precision_at_3, 4),
        "recall_at_3": round(recall_at_3, 4),
        "relevant_recommendations": relevant_recommendations,
        "total_recommended": len(top_three),
        "total_relevant": len(relevant),
    }
