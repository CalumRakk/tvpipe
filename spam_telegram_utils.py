import json
from pathlib import Path

CACHE_FILE = Path("meta/sent_users_cache.json")
CACHE_FILE_PEERFOOD = Path("meta/peerflood_users_cache.json")


def load_sent_user_ids() -> set[int]:
    """Load cached user IDs from file."""
    if not CACHE_FILE.exists():
        return set()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, TypeError):
        return set()


def load_sent_user_ids_peerfood() -> set[int]:
    """Load cached user IDs from file."""
    if not CACHE_FILE_PEERFOOD.exists():
        return set()
    try:
        with open(CACHE_FILE_PEERFOOD, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, TypeError):
        return set()


def save_sent_user_ids(user_ids: set[int]) -> None:
    """Save cached user IDs to file."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(user_ids), f)


def save_sent_user_ids_peerfood(user_ids: set[int]) -> None:
    """Save cached user IDs to file."""
    with open(CACHE_FILE_PEERFOOD, "w", encoding="utf-8") as f:
        json.dump(list(user_ids), f)


def has_user_been_messaged(user_id: int, cache: set[int]) -> bool:
    """Check if a user has already been messaged."""
    return user_id in cache


def has_user_been_peerfood(user_id: int, cache: set[int]) -> bool:
    """Check if a user has already been messaged."""
    return user_id in cache


def mark_user_as_messaged(user_id: int, cache: set[int]) -> None:
    """Add a user ID to the cache and save it."""
    cache.add(user_id)
    save_sent_user_ids(cache)


def mark_user_as_peerfood(user_id: int, cache: set[int]) -> None:
    """Add a user ID to the cache and save it."""
    cache.add(user_id)
    save_sent_user_ids_peerfood(cache)
