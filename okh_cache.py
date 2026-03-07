"""Shared cache for OnlineKhabar API party data.
Separate module to avoid circular import issues between app.py and scraper.py."""

from datetime import datetime, timezone

_okh_party_cache = {
    "data": None,
    "timestamp": None,
}


def set_okh_party_cache(data):
    _okh_party_cache["data"] = data
    _okh_party_cache["timestamp"] = datetime.now(timezone.utc).isoformat()


def get_okh_party_cache():
    return _okh_party_cache.get("data")


def get_okh_cache_timestamp():
    return _okh_party_cache.get("timestamp")
