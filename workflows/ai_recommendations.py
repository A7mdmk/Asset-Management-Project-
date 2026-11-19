
from assets.models import Asset, StockBalance
import json
from .gemini_client import GEMINI_MODEL, get_gemini_client

def get_available_assets():
    """
    Return campus assets eligible for recommendations.
    """

    assets = Asset.objects.filter(
        publication=Asset.Publication.PUBLISHED,
        lifecycle=Asset.Lifecycle.ACTIVE,
        condition__in=[
            Asset.Condition.GOOD,
            Asset.Condition.FAIR,
        ],
        stock__free__gt=0,
    ).select_related(
        "category",
        "department",
    ).order_by("name")

    available_assets = []

    for asset in assets:
        available_assets.append({
            "id": str(asset.pk),
            "name": asset.name,
            "description": asset.description,
            "category": asset.category.name,
            "department": asset.department.name,
            "location": asset.location,
            "available_quantity": asset.stock.free,
        })

    return available_assets

def recommend_assets(user_need):
    """
    Recommend eligible campus assets using Gemini AI.
    AI recommendations never reserve or approve stock.
    """

    if not isinstance(user_need, str) or not user_need.strip():
        raise ValueError("Please describe the resource you need.")

    available_assets = get_available_assets()

    if not available_assets:
        return {
            "recommendations": [],
            "message": "No published assets are currently available.",
        }

    prompt = f"""
You are an asset recommendation assistant for KU ResourceSavers.

User request:
{user_need}

Available assets (JSON):
{json.dumps(available_assets, ensure_ascii=False)}

Recommend up to 3 assets that best match the user's needs.

Rules:
- Only recommend assets from the provided JSON.
- Do not invent assets, IDs, or quantities.
- Consider the name, description, category, and location.
- Do not approve requests or reserve stock.
- Return only the asset IDs as a JSON array.
"""

    client = get_gemini_client()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    try:
        suggested_ids = json.loads(response.text)
    except (ValueError, TypeError):
        raise ValueError("Gemini returned an invalid response.")

    if not isinstance(suggested_ids, list):
        raise ValueError("Gemini must return a JSON array.")

    assets_by_id = {
        asset["id"]: asset for asset in available_assets
    }

    recommendations = []
    seen = set()

    for asset_id in suggested_ids:
        if not isinstance(asset_id, str):
            continue

        if asset_id in assets_by_id and asset_id not in seen:
            recommendations.append(assets_by_id[asset_id])
            seen.add(asset_id)

        if len(recommendations) == 3:
            break

    return {
        "recommendations": recommendations,
        "message": "Recommendations generated successfully.",
    }
