"""
Minimal Upstash Redis REST client.
Uses the same REST-API pattern (not redis-py/TLS) as your other dashboards,
so this Python job and your Next.js frontend can share one Upstash instance
without needing a Python Redis driver.

Requires two environment variables (same names work for both this script
and Vercel/Dokku env config):
  UPSTASH_REDIS_REST_URL
  UPSTASH_REDIS_REST_TOKEN
"""
import os
import json
import requests

KEY_PREFIX = "rt_"


def _base_url():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    if not url:
        raise RuntimeError("UPSTASH_REDIS_REST_URL not set")
    return url.rstrip("/")


def _headers():
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not token:
        raise RuntimeError("UPSTASH_REDIS_REST_TOKEN not set")
    return {"Authorization": f"Bearer {token}"}


def set_json(key: str, value, ttl_seconds: int = None):
    """Store a JSON-serializable value under rt_<key>."""
    full_key = f"{KEY_PREFIX}{key}"
    payload = json.dumps(value)
    url = f"{_base_url()}/set/{full_key}"
    resp = requests.post(url, headers=_headers(), data=payload.encode("utf-8"))
    resp.raise_for_status()
    if ttl_seconds:
        requests.post(f"{_base_url()}/expire/{full_key}/{ttl_seconds}", headers=_headers())
    return resp.json()


def get_json(key: str):
    """Retrieve and JSON-decode a value stored under rt_<key>. Returns None if missing."""
    full_key = f"{KEY_PREFIX}{key}"
    url = f"{_base_url()}/get/{full_key}"
    resp = requests.get(url, headers=_headers())
    resp.raise_for_status()
    result = resp.json().get("result")
    if result is None:
        return None
    return json.loads(result)
