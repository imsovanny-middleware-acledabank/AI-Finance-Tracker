import google.generativeai as genai
import json
import os
from datetime import date
from dotenv import load_dotenv

# Load environment from .env (if present)
load_dotenv()

def analyze_finance_text(text):
    # Ensure API key is available at call time
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API_KEY or ADC found. Please either:\n"
            "  - Set the `GEMINI_API_KEY` environment variable.\n"
            "  - Manually call `genai.configure(api_key=...)` before using this function.\n"
            "  - Or set up Application Default Credentials: https://ai.google.dev/gemini-api/docs/oauth"
        )

    genai.configure(api_key=api_key)

    # Try a set of candidate models (some projects use slightly different model IDs).
    # Prefer stable Gemini v2/v3 model IDs available in this project environment
    candidate_models = [
        'models/gemini-2.5-flash',
        'models/gemini-2.5-pro',
        'models/gemini-2.0-flash',
        'models/gemini-flash-latest',
        'models/gemini-pro-latest',
        'models/gemini-2.5-flash-lite',
        'models/gemini-3-pro-preview',
    ]

    prompt = f"""
    You are a financial assistant. Analyze the following text and determine if it describes a financial transaction.
    Today's date is {date.today()}.
    
    Text: "{text}"
    
    If the text describes a financial transaction (income, expense, purchase, etc.), extract the details and return a JSON object with these keys:
    {{
        "amount": float,
        "category": "Food/Transport/Bills/Salary/etc",
        "type": "income" or "expense",
        "note": "brief description",
        "date": "YYYY-MM-DD",
        "is_transaction": true
    }}
    
    If the text is NOT a financial transaction (e.g., a question, greeting, or query), respond with:
    {{
        "is_transaction": false,
        "message": "brief explanation why this is not a transaction"
    }}
    
    Return ONLY valid JSON, no other text.
    """
    
    # Attempt to generate content using the first working model from the candidates.
    response = None
    last_exc = None
    for mname in candidate_models:
        try:
            model = genai.GenerativeModel(mname)
            response = model.generate_content(prompt)
            break
        except Exception as e:
            last_exc = e

    if response is None:
        # Try to list available models to provide a helpful error message.
        # Try to list available models and produce a readable summary
        try:
            available_raw = genai.list_models()
            try:
                available_list = list(available_raw)
                model_names = []
                for item in available_list:
                    if isinstance(item, dict):
                        name = item.get('name') or str(item)
                    else:
                        name = getattr(item, 'name', None) or str(item)
                    model_names.append(name)
                available = ', '.join(model_names[:50]) or 'none'
            except Exception:
                available = str(available_raw)
        except Exception:
            available = 'unavailable (failed to list models)'

        raise RuntimeError(
            f"No candidate model worked. Last error: {last_exc}\n"
            f"Tried models: {candidate_models}\n"
            f"Available models: {available}\n"
            "Please update the model name or check the API version/permissions."
        )
    
    # Clean the response to ensure it's valid JSON
    json_text = response.text.replace('```json', '').replace('```', '').strip()
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"AI response was not valid JSON. Raw response:\n{response.text}\n"
            f"Cleaned text:\n{json_text}\n"
            f"Parse error: {e}"
        )

    # Check if this is a transaction or a non-transaction query
    if not parsed.get('is_transaction', True):  # default True for backward compat
        # User sent a query, not a transaction
        return {
            'is_transaction': False,
            'message': parsed.get('message', 'This does not appear to be a financial transaction.')
        }

    # Validate required fields for transactions
    required_fields = ['amount', 'category', 'type']
    missing = [f for f in required_fields if not parsed.get(f)]
    if missing:
        raise ValueError(
            f"AI response missing required fields: {missing}\n"
            f"Full response: {parsed}"
        )

    return parsed