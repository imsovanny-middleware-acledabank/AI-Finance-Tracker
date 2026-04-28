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
        'models/gemini-2.0-flash',
        'models/gemini-2.5-flash-lite',
        'models/gemini-3-flash-preview',
        'models/gemini-3.1-flash-lite-preview',
        'models/gemini-2.0-flash-lite',
        'models/gemini-flash-latest',
        'models/gemini-flash-lite-latest',
        'models/gemini-2.5-pro',
        'models/gemini-pro-latest',
        'models/gemini-3-pro-preview',
        'models/gemini-3.1-pro-preview',
        'models/gemini-3.1-flash-lite'
    ]

    prompt = f"""
    You are a financial assistant specialized in Cambodian and US currency.
    Today's date is {date.today()}.
    
    Exchange rate reference: 1 USD ≈ 4,100 KHR (Cambodian Riel).
    
    IMPORTANT LANGUAGE RULE: Detect the language of the user's text. If the user writes in Khmer (ខ្មែរ), respond with "message" in Khmer. If in English, respond in English. Always match the user's language.
    
    Text: "{text}"
    
    Analyze the text and return ONE of the following JSON responses:

    === 1. FINANCIAL TRANSACTION ===
    If the text describes a financial transaction (income, expense, purchase, payment, etc.), return:
    {{
        "is_transaction": true,
        "amount": float,
        "currency": "USD" or "KHR",
        "amount_usd": float,
        "amount_khr": float,
        "category": "Food/Transport/Bills/Salary/Shopping/Entertainment/Health/Education/Other",
        "type": "income" or "expense",
        "note": "brief description in user's language",
        "date": "YYYY-MM-DD"
    }}
    Currency rules: "រៀល"/"៛"/"KHR"/"riel" → KHR; "$"/"USD"/"dollar"/"ដុល្លា" → USD; default USD.
    Always provide both amount_usd and amount_khr (convert using the real-time USD→KHR rate from the API; fallback is 4100 if unavailable).

    === 2. SUMMARY/REPORT REQUEST (with time period) ===
    If the user asks about spending/income for a SPECIFIC TIME PERIOD (today, this month, this year, a specific date), return:
    {{
        "is_transaction": false,
        "is_summary": true,
        "period": "day" or "month" or "year",
        "date": "YYYY-MM-DD",
        "message": "summary request"
    }}
    CRITICAL period detection:
    - "today", "ថ្ងៃនេះ", "daily", "ប្រចាំថ្ងៃ", "ចំណាយថ្ងៃនេះ" → period: "day"
    - "this month", "ខែនេះ", "monthly", "ប្រចាំខែ", "ចំណាយខែនេះ", "នៅខែនេះ" → period: "month"
    - "this year", "ឆ្នាំនេះ", "yearly", "ប្រចាំឆ្នាំ" → period: "year"
    - Key: If user mentions "ខែនេះ" (this month) or "ថ្ងៃនេះ" (today), it is ALWAYS a summary, NOT a balance query.
    - "តើនៅខែនេះខ្ញុំចំណាយអស់ប៉ុន្មាន" = "How much did I spend THIS MONTH" → is_summary with period "month"
    - "តើនៅថ្ងៃនេះខ្ញុំចំណាយអស់ប៉ុន្មាន" = "How much did I spend TODAY" → is_summary with period "day"
    - Date: use today's date for "today"/"ថ្ងៃនេះ", today's date for "this month"/"ខែនេះ", today's date for "this year"/"ឆ្នាំនេះ"

    === 3. BALANCE QUERY (overall, no time period) ===
    If the user asks about their OVERALL balance/remaining/total WITHOUT a specific time period, return:
    {{
        "is_transaction": false,
        "is_balance": true,
        "message": "balance query"
    }}
    Examples: "នៅសល់ប៉ុន្មាន", "balance", "remaining", "my balance", "ទឹកប្រាក់នៅសល់", "ស្ថានភាពហិរញ្ញវត្ថុ"

    === 4. EXCHANGE RATE ===
    If asking about exchange rates:
    {{
        "is_transaction": false,
        "message": "💱 អត្រាប្តូរប្រាក់ / Exchange Rate: 1 USD = 4,100 KHR (រៀល). ឧទាហរណ៍: $10 = 41,000៛"
    }}

    === 5. OTHER (greeting, question, etc.) ===
    For anything else:
    {{
        "is_transaction": false,
        "message": "a helpful response in the user's language"
    }}
    
    Return ONLY valid JSON, no other text.
    """
    
    # Attempt to generate content using the first working model from the candidates.
    import time
    response = None
    last_exc = None
    for attempt in range(2):  # retry once after short delay on quota errors
        for mname in candidate_models:
            try:
                model = genai.GenerativeModel(mname)
                response = model.generate_content(prompt)
                break
            except Exception as e:
                last_exc = e
        if response is not None:
            break
        # If first pass failed (likely quota), wait briefly and retry with remaining models
        if attempt == 0:
            time.sleep(2)

    if response is None:
        # Keep error short to avoid Telegram message-too-long crash
        last_err_short = str(last_exc)[:200] if last_exc else 'unknown'
        if '429' in last_err_short or 'quota' in last_err_short.lower():
            raise RuntimeError(
                "⏳ សេវា AI រវល់បណ្តោះអាសន្ន (rate limit)។ សូមព្យាយាមម្តងទៀតក្នុង 1 នាទី។\n"
                "AI quota exceeded. Please try again in 1 minute."
            )
        raise RuntimeError(
            f"AI service error: {last_err_short}"
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
        # User sent a query, not a transaction — pass through all fields
        return parsed

    # Validate required fields for transactions
    required_fields = ['amount', 'category', 'type']
    missing = [f for f in required_fields if not parsed.get(f)]
    if missing:
        raise ValueError(
            f"AI response missing required fields: {missing}\n"
            f"Full response: {parsed}"
        )

    return parsed


def analyze_reply_action(reply_text, original_message):
    """Analyze a reply to a transaction message to determine edit/delete intent."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)

    candidate_models = [
        'models/gemini-2.5-flash',
        'models/gemini-2.0-flash',
        'models/gemini-2.5-flash-lite',
        'models/gemini-3-flash-preview',
        'models/gemini-3.1-flash-lite-preview',
        'models/gemini-2.0-flash-lite',
        'models/gemini-flash-latest',
        'models/gemini-flash-lite-latest',
        'models/gemini-2.5-pro',
        'models/gemini-pro-latest',
        'models/gemini-3-pro-preview',
        'models/gemini-3.1-pro-preview',
    ]

    prompt = f"""
    You are an AI assistant for a finance bot.
    
    A user previously recorded a transaction. The bot's confirmation message was:
    ---
    {original_message}
    ---
    
    Now the user replied to that message with:
    "{reply_text}"
    
    Determine what the user wants to do. Return ONLY valid JSON:

    If the user wants to DELETE the transaction (e.g., "delete", "remove", "cancel", "លុប", "ដកចេញ", "ខុស"):
    {{
        "action": "delete",
        "reason": "brief reason"
    }}

    If the user wants to EDIT/UPDATE the transaction (e.g., "change amount to 20", "category should be Food", "កែ", "ផ្លាស់ប្ដូរ"):
    {{
        "action": "edit",
        "changes": {{
            "amount": float or null,
            "category": "string" or null,
            "date": "YYYY-MM-DD" or null,
            "note": "string" or null
        }}
    }}
    Only include fields the user wants to change (set others to null).

    If the reply is unclear or not related to editing/deleting:
    {{
        "action": "unknown",
        "message": "brief explanation"
    }}

    Return ONLY valid JSON, no other text.
    """

    import time
    response = None
    last_exc = None
    for attempt in range(2):
        for mname in candidate_models:
            try:
                model = genai.GenerativeModel(mname)
                response = model.generate_content(prompt)
                break
            except Exception as e:
                last_exc = e
        if response is not None:
            break
        if attempt == 0:
            time.sleep(2)

    if response is None:
        raise RuntimeError("AI service temporarily unavailable. Please try again in a moment.")

    json_text = response.text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI reply analysis was not valid JSON: {json_text}")