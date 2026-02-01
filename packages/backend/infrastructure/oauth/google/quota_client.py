"""
Google Quota Client

Fetches Gemini user quota information from cloudcode-pa API.
"""

from dataclasses import dataclass
from typing import List, Optional

import aiohttp


QUOTA_ENDPOINT = "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota"


@dataclass
class QuotaWindow:
    label: str
    used_percent: float
    remaining_percent: float
    remaining_fraction: float


@dataclass
class QuotaSummary:
    windows: List[QuotaWindow]


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


class GoogleQuotaClient:
    """Client for retrieving Gemini quota data."""

    def __init__(self, endpoint: str = QUOTA_ENDPOINT):
        self._endpoint = endpoint

    async def fetch_quota(self, access_token: str) -> QuotaSummary:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._endpoint, headers=headers, json={}) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise ValueError(f"Quota request failed: {response.status} {error_text}")

                data = await response.json()

        buckets = data.get("buckets", []) if isinstance(data, dict) else []
        pro_min: Optional[float] = None
        flash_min: Optional[float] = None

        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            model_id = str(bucket.get("modelId") or "").lower()
            remaining = bucket.get("remainingFraction", 1)
            try:
                remaining_fraction = float(remaining)
            except (TypeError, ValueError):
                remaining_fraction = 1.0

            if "pro" in model_id:
                pro_min = remaining_fraction if pro_min is None else min(pro_min, remaining_fraction)
            if "flash" in model_id:
                flash_min = remaining_fraction if flash_min is None else min(flash_min, remaining_fraction)

        windows: List[QuotaWindow] = []

        if pro_min is not None:
            used = _clamp_percent((1.0 - pro_min) * 100.0)
            remaining = _clamp_percent(pro_min * 100.0)
            windows.append(
                QuotaWindow(
                    label="Pro",
                    used_percent=used,
                    remaining_percent=remaining,
                    remaining_fraction=pro_min,
                )
            )

        if flash_min is not None:
            used = _clamp_percent((1.0 - flash_min) * 100.0)
            remaining = _clamp_percent(flash_min * 100.0)
            windows.append(
                QuotaWindow(
                    label="Flash",
                    used_percent=used,
                    remaining_percent=remaining,
                    remaining_fraction=flash_min,
                )
            )

        return QuotaSummary(windows=windows)
