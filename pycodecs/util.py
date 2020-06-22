from collections import Iterable
from math import copysign


class RoundRobinList(Iterable):

    def __init__(self, max_size: int = 10):
        self._entries = list()
        self._next_write = 0
        self._max_size = max_size

    def __iter__(self):
        return self

    def __getitem__(self, item: int):
        return self._entries[(self._next_write + item) % int(copysign(self.max_size, self._next_write + item))]

    def __len__(self):
        return len(self._entries)

    def append(self, item):
        if len(self._entries) < self.max_size:
            self._entries.append(item)
        else:
            self._entries[self._next_write] = item
            self._next_write = (self.next_write + 1) % self.max_size

    @property
    def next_write(self):
        return self._next_write

    @property
    def max_size(self):
        return self._max_size


class RoundRobinListIterator:

    def __init__(self, rrl: RoundRobinList):
        self._rrl = rrl
        self._current = (rrl.next_write - 1) % self._rrl.max_size

    def __next__(self):
        result = self._rrl[self._current]
        self._current = (self._current - 1) % self._rrl.max_size
        return result
