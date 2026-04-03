import time
from app.services.cache import TTLCache


def test_set_and_get():
    cache = TTLCache(ttl=10)
    cache.set("k1", {"result": "ok"})
    assert cache.get("k1") == {"result": "ok"}


def test_miss_returns_none():
    cache = TTLCache()
    assert cache.get("nonexistent") is None


def test_ttl_expiry():
    cache = TTLCache(ttl=0)  # expires immediately
    cache.set("k1", "val")
    time.sleep(0.01)
    assert cache.get("k1") is None


def test_invalidate():
    cache = TTLCache(ttl=300)
    cache.set("k1", "val")
    cache.invalidate("k1")
    assert cache.get("k1") is None


def test_clear():
    cache = TTLCache(ttl=300)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.size == 2
    cache.clear()
    assert cache.size == 0


def test_size_prunes_expired():
    cache = TTLCache(ttl=0)
    cache.set("a", 1)
    cache.set("b", 2)
    time.sleep(0.01)
    assert cache.size == 0
