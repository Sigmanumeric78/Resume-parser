from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
ENDPOINT = f"{BASE_URL.rstrip('/')}/api/search"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _is_list_of_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate_response(data: Dict[str, Any]) -> None:
    _assert(isinstance(data, dict), "Response is not a JSON object")
    _assert(isinstance(data.get("total_results"), int), "total_results must be int")
    _assert(isinstance(data.get("results"), list), "results must be a list")

    for idx, item in enumerate(data["results"], start=1):
        _assert(isinstance(item, dict), f"result #{idx} is not an object")
        _assert(
            isinstance(item.get("candidate_id"), str) and item["candidate_id"],
            f"result #{idx} missing candidate_id",
        )
        _assert(
            isinstance(item.get("display_name"), str),
            f"result #{idx} missing display_name",
        )
        _assert(
            isinstance(item.get("score"), (int, float)),
            f"result #{idx} missing score",
        )
        _assert(
            _is_list_of_strings(item.get("skills")),
            f"result #{idx} skills must be list[str]",
        )
        _assert(
            _is_list_of_strings(item.get("highlights")),
            f"result #{idx} highlights must be list[str]",
        )


def main() -> int:
    payload = {"query": "Media Activities Specialist", "top_n": 5}
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(ENDPOINT, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        print(f"ERROR: Request failed: {exc}")
        return 1

    try:
        validate_response(data)
    except AssertionError as exc:
        print(f"Schema validation failed: {exc}")
        return 2

    print("OK: /api/search response schema validated.")
    print(f"Total results: {data.get('total_results')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
