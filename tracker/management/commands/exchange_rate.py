"""Exchange rate service — USD to KHR with caching and fallback."""
import logging
import os
import time
from decimal import Decimal

import aiohttp

USD_KHR_FALLBACK_RATE = Decimal("4012")

logger = logging.getLogger(__name__)

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
        now = time.time()
        if (
            not force_refresh
            and _EXCHANGE_RATE_CACHE["usd_to_khr"]
            and (now - _EXCHANGE_RATE_CACHE["timestamp"] < cls.CACHE_TTL)
        ):
            logger.debug("Using cached USD→KHR exchange rate")
            return _EXCHANGE_RATE_CACHE["usd_to_khr"]

        api_key = os.getenv("EXCHANGERATE_API_KEY")
        if not api_key:
            logger.warning(
                "EXCHANGERATE_API_KEY is not configured; using fallback USD→KHR rate"
            )
            return cls._use_fallback(now)

        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    khr = data.get("conversion_rates", {}).get("KHR")
                    if (
                        resp.status != 200
                        or khr is None
                        or not isinstance(khr, (int, float))
                    ):
                        logger.warning(
                            "Exchange rate API returned invalid USD→KHR data; using fallback"
                        )
                        return cls._use_fallback(now)
                    rate = Decimal(str(khr))
                    _EXCHANGE_RATE_CACHE["usd_to_khr"] = rate
                    _EXCHANGE_RATE_CACHE["timestamp"] = now
                    return rate
        except Exception:
            logger.exception("Exchange rate API request failed; using fallback")
            return cls._use_fallback(now)

    @classmethod
    def _use_fallback(cls, now: float) -> Decimal:
        _EXCHANGE_RATE_CACHE["usd_to_khr"] = cls.FALLBACK_RATE
        _EXCHANGE_RATE_CACHE["timestamp"] = now
        return cls.FALLBACK_RATE


# Module-level shortcut so other modules can do: from .exchange_rate import fetch_usd_to_khr_rate
async def fetch_usd_to_khr_rate(force_refresh: bool = False) -> Decimal:
    return await ExchangeRateService.fetch_usd_to_khr_rate(force_refresh)
