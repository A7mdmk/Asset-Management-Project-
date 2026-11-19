
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_MODEL = "gemini-3.5-flash-lite"

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=15000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
