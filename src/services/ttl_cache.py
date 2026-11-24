"""Small in-process TTL cache for external API results."""

from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic


class TTLCache:
    def __init__(self, maxsize=128, clock=monotonic):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self._clock = clock
        self._items = OrderedDict()
        self._lock = RLock()

    def get_or_set(self, key, factory, *, ttl_seconds):
        """Return (copied value, cache_hit). Exceptions are never cached."""

        if ttl_seconds <= 0:
            return factory(), False

        now = self._clock()
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                expires_at, value = item
                if expires_at > now:
                    self._items.move_to_end(key)
                    return deepcopy(value), True
                del self._items[key]

        value = factory()
        stored_value = deepcopy(value)

        with self._lock:
            self._items[key] = (
                self._clock() + ttl_seconds,
                stored_value,
            )
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

        return deepcopy(stored_value), False

    def clear(self):
        with self._lock:
            self._items.clear()
