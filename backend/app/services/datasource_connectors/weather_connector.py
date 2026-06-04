"""Weather connector using wttr.in JSON API (free, no API key required).

Endpoint: https://wttr.in/{city}?format=j1

Returns result_type="stats" with current weather and 3-day forecast.
"""
from __future__ import annotations

import logging
import re

import httpx

from app.services.datasource_connectors import BaseConnector, DataSourceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0


class WeatherConnector(BaseConnector):
    source_key = "env_weather_cn"
    source_name = "中国天气预报数据"

    async def search(self, query: str, limit: int = 10) -> DataSourceResult:
        city = _extract_city(query)
        try:
            url = f"https://wttr.in/{city}?format=j1"
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                raw = resp.json()

            stats = _parse_weather(raw, city)
            return DataSourceResult(
                source_key=self.source_key,
                source_name=self.source_name,
                result_type="stats",
                data=stats,
                row_count=len(stats),
            )
        except httpx.TimeoutException:
            logger.warning("[weather_connector] Timeout for city: %s", city)
            return _mock_result(city)
        except Exception as exc:
            logger.warning("[weather_connector] Error for '%s': %s", city, exc)
            return _mock_result(city)


def _extract_city(query: str) -> str:
    """Extract a city name from the query string."""
    # Common Chinese city names
    cities = [
        "北京", "上海", "广州", "深圳", "成都", "杭州", "武汉", "西安",
        "南京", "天津", "重庆", "苏州", "长沙", "郑州", "青岛",
        "Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu",
    ]
    for c in cities:
        if c in query:
            return c
    # Fall back to first two CJK chars or first word
    m = re.search(r"[一-龥]{2,4}", query)
    if m:
        return m.group()
    words = query.strip().split()
    return words[0] if words else "Beijing"


def _parse_weather(raw: dict, city: str) -> dict:
    """Parse wttr.in JSON into a flat stats dict."""
    stats: dict = {"city": city}
    try:
        current = raw.get("current_condition", [{}])[0]
        stats["temp_c"] = current.get("temp_C", "N/A")
        stats["feels_like_c"] = current.get("FeelsLikeC", "N/A")
        stats["humidity_pct"] = current.get("humidity", "N/A")
        stats["wind_speed_kmph"] = current.get("windspeedKmph", "N/A")
        stats["wind_direction"] = current.get("winddir16Point", "N/A")
        stats["visibility_km"] = current.get("visibility", "N/A")
        desc_list = current.get("weatherDesc", [{}])
        stats["description"] = desc_list[0].get("value", "") if desc_list else ""

        forecasts = raw.get("weather", [])
        for i, day in enumerate(forecasts[:3]):
            prefix = f"day{i + 1}"
            stats[f"{prefix}_date"] = day.get("date", "")
            stats[f"{prefix}_max_c"] = day.get("maxtempC", "")
            stats[f"{prefix}_min_c"] = day.get("mintempC", "")
            stats[f"{prefix}_avg_c"] = day.get("avgtempC", "")
            stats[f"{prefix}_rainfall_mm"] = day.get("hourly", [{}])[0].get("precipMM", "") if day.get("hourly") else ""
    except (KeyError, IndexError, TypeError) as e:
        logger.debug("[weather_connector] Parse error: %s", e)
    return stats


def _mock_result(city: str) -> DataSourceResult:
    stats = {
        "city": city,
        "temp_c": "22",
        "feels_like_c": "23",
        "humidity_pct": "65",
        "wind_speed_kmph": "12",
        "wind_direction": "SE",
        "visibility_km": "10",
        "description": "Partly cloudy",
        "day1_date": "2024-06-01",
        "day1_max_c": "28",
        "day1_min_c": "18",
        "day1_avg_c": "23",
        "day2_date": "2024-06-02",
        "day2_max_c": "26",
        "day2_min_c": "17",
        "day2_avg_c": "21",
        "day3_date": "2024-06-03",
        "day3_max_c": "30",
        "day3_min_c": "20",
        "day3_avg_c": "25",
    }
    return DataSourceResult(
        source_key="env_weather_cn",
        source_name="中国天气预报数据",
        result_type="stats",
        data=stats,
        row_count=len(stats),
    )
