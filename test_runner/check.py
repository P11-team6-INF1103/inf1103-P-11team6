#Ren Xiang

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from test_runner.result import Result

if TYPE_CHECKING:
    from test_runner.runner import Runner


# One thing to check. Subclasses say how to run it; the runner never needs to know which kind it has.
class Check(ABC):
    def __init__(self, name: str, owner: str, phase: int) -> None:
        self.name = name
        self.owner = owner
        self.phase = phase

    @abstractmethod
    def describe(self) -> str:
        ...

    @abstractmethod
    def run(self, runner: "Runner") -> Result:
        ...