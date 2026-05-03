"""Exchange rate service — USD to KHR with caching and fallback."""
import os
import time
from decimal import Decimal

import aiohttp

USD_KHR_FALLBACK_RATE = Decimal("4012")

_EXCHANGE_RATE_CACHE: dict = {
    "usd_to_khr": None,
    "timestamp": 0,
}


class ExchangeRateService:
    """Handles fetching and caching the USD→KHR exchange rate."""

    FALLBACK_RATE = USD_KHR_FALLBACK_RATE
    CACHE_TTL = 600  # 10 minutes

    @classmethod
    async def fetch_usd_to_khr_rate(cls, force_refresh: bool = False) -> Decimal:
        """Fetch USD→KHR from exchangerate-api.com with in-memory cache and fallback."""
        import json

        now = time.time()
        if (
            not force_refresh
            and _EXCHANGE_RATE_CACHE["usd_to_khr"]
            and (now - _EXCHANGE_RATE_CACHE["timestamp"] < cls.CACHE_TTL)
        ):
            print("[DEBUG] Using cached rate:", _EXCHANGE_RATE_CACHE["usd_to_khr"])
            return _EXCHANGE_RATE_CACHE["usd_to_khr"]

        api_key = os.getenv("EXCHANGERATE_API_KEY", "6c907c135d5ef9e007ef3c83")
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        try:
            print(f"[DEBUG] ExchangeRate API url: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    print(f"[DEBUG] ExchangeRate API status: {resp.status}")
                    data = await resp.json()
                    print(f"[DEBUG] ExchangeRate API raw response: {json.dumps(data)}")
                    khr = data.get("conversion_rates", {}).get("KHR")
                    print(f"[DEBUG] ExchangeRate API KHR: {khr}")
                    if (
                        resp.status != 200
                        or khr is None
                        or not isinstance(khr, (int, float))
                    ):
                        print("[DEBUG] API call failed or invalid KHR rate, using fallback.")
                        return cls._use_fallback(now)
                    rate = Decimal(str(khr))
                    _EXCHANGE_RATE_CACHE["usd_to_khr"] = rate
                    _EXCHANGE_RATE_CACHE["timestamp"] = now
                    return rate
        except Exception as e:
            print(f"[DEBUG] ExchangeRate API error: {e}")
            return cls._use_fallback(now)

    @classmethod
    def _use_fallback(cls, now: float) -> Decimal:
        _EXCHANGE_RATE_CACHE["usd_to_khr"] = cls.FALLBACK_RATE
        _EXCHANGE_RATE_CACHE["timestamp"] = now
        return cls.FALLBACK_RATE


# Module-level shortcut so other modules can do: from .exchange_rate import fetch_usd_to_khr_rate
async def fetch_usd_to_khr_rate(force_refresh: bool = False) -> Decimal:
    return await ExchangeRateService.fetch_usd_to_khr_rate(force_refresh)
