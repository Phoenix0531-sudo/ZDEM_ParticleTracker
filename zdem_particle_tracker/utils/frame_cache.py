"""Bounded LRU cache for ParticleData frames."""
from __future__ import annotations

from collections import OrderedDict
from typing import Generic, Hashable, Optional, TypeVar

T = TypeVar("T")


class LRUCache(Generic[T]):
    """Simple ordered LRU cache with fixed capacity."""

    def __init__(self, capacity: int = 5) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = int(capacity)
        self._data: OrderedDict[Hashable, T] = OrderedDict()

    def __contains__(self, key: Hashable) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: Hashable, default: Optional[T] = None) -> Optional[T]:
        if key not in self._data:
            return default
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: Hashable, value: T) -> None:
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
        else:
            self._data[key] = value
            if len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def keys(self):
        return list(self._data.keys())
