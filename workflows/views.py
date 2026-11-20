
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .ai_recommendations import recommend_assets


@login_required
def ai_recommendations_view(request):
    context = {
        "user_need": "",
        "recommendations": [],
        "message": "",
        "error": "",
    }

    if request.method == "POST":
        user_need = request.POST.get("user_need", "").strip()
        context["user_need"] = user_need

        if not user_need:
            context["error"] = "Please describe the resource you need."
        elif len(user_need) > 500:
            context["error"] = "Your request must be 500 characters or fewer."
        else:
            try:
                result = recommend_assets(user_need)
                context["recommendations"] = result["recommendations"]
                context["message"] = result["message"]
            except Exception:
                context["error"] = (
                    "AI recommendations are temporarily unavailable. "
                    "Please try again later."
                )

    return render(
        request,
        "workflows/recommendations.html",
        context,
    )
