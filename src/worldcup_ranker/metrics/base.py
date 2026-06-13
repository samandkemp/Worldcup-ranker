from abc import ABC, abstractmethod
from typing import List, Dict, Any, Type

from worldcup_ranker.models import Team, Player


class Metric(ABC):
    name: str

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def compute(self, team: Team, players: List[Player], context: Dict[str, Any] = None) -> float:
        raise NotImplementedError()


class MetricRegistry:
    _registry: Dict[str, Type[Metric]] = {}

    @classmethod
    def register(cls, metric_cls: Type[Metric]):
        cls._registry[metric_cls.__name__] = metric_cls
        return metric_cls

    @classmethod
    def get(cls, name: str):
        return cls._registry.get(name)

    @classmethod
    def list(cls):
        return list(cls._registry.keys())

    @classmethod
    def create(cls, name: str, *args, **kwargs):
        mcls = cls.get(name)
        if not mcls:
            raise KeyError(f"Metric {name} not registered")
        return mcls(*args, **kwargs)
