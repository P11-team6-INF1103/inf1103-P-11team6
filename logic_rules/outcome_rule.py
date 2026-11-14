# Sufi

from abc import ABC, abstractmethod

from models.incident import Incident


class OutcomeRule(ABC):
    # Interface for one routing rule. LogicManager asks each rule in turn; the first that applies wins.

    # The outcome name this rule gives, e.g. 'stop_work_review'.
    @property
    @abstractmethod
    def outcome(self) -> str:
        ...

    # True if this rule decides the outcome for the incident.
    @abstractmethod
    def applies(self, incident: Incident, history: list) -> bool:
        ...
