from __future__ import annotations

import multiprocessing
import multiprocessing.managers
import multiprocessing.queues
import queue
from typing import Any, Iterable

"""
Class for handling multiple multiprocessing.Queue objects together.
It could be modified to take queue.Queue objects as well.
"""


class MultiQueue:
    def __init__(self, queues: Iterable[multiprocessing.Queue[Any]] = []) -> None:
        manager = multiprocessing.get_context("spawn").Manager()
        self.queues = manager.dict()
        for queue in queues:
            self.add_queue(queue)

    def add_queue(self, queue: multiprocessing.Queue[Any]) -> None:
        """
        Add a queue
        """
        if not isinstance(queue, multiprocessing.managers.BaseProxy):
            raise ValueError("Input must be a multiprocessing.managers.Queue object")
        self.queues[id(queue)] = queue

    def remove_queue(self, queue: multiprocessing.Queue[Any]) -> None:
        """
        Remove a queue by reference
        """
        if self.queues.pop(id(queue), None) is None:
            raise ValueError("Queue not found in MultiQueue")

    def put(self, item: Any) -> None:
        """
        Put an item into all queues
        """
        ##TODO: properly handle if one of the queues is full
        for q in self.queues.values():
            try:
                q.put(item, block=False)
            except queue.Full:  # multiprocessing.queues.Full:
                pass  # we ignore full queues for now, since multiprocessing queues can't be used similarly to collections.Deque objects or be cleared easily.
            except TypeError as e:  # TODO: multiprocessing debug (JIRA issue ALTS-150)
                print("[MultiQueue]:", e)
                # Maybe setting a maxsize to all queues would solve this?

    def empty(self) -> bool:
        """
        Check if the every queue in MultiQueue is empty.
        """
        if not self.queues:
            raise ValueError("No queues added to MultiQueue")
        return all(queue.empty() for queue in self.queues)
