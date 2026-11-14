# Ren Xiang
import logging
from abc import ABC, abstractmethod

from models.incident import Incident

logger = logging.getLogger(__name__)


class EnrichmentStep(ABC):
    # One AI job for an incident. Subclasses build the prompt and clean the reply;
    # this base class makes sure no step can ever crash the pipeline.

    # A short name used in the log.
    name = "step"

    # Most steps always run; a step overrides this to skip incidents it does not apply to.
    def should_run(self, incident: Incident) -> bool:
        return True

    # Calls the API and returns the fields to add to the incident; may raise.
    @abstractmethod
    def run(self, incident: Incident, history: list[Incident]) -> dict:
        ...

    # The fields to add when the step failed, with the error message in them.
    @abstractmethod
    def error_fields(self, message: str) -> dict:
        ...

    # The fields to add when the step was skipped; by default nothing.
    def skipped_fields(self) -> dict:
        return {}

    # Runs the step and never raises: a failure becomes the step's error fields.
    def safe_run(self, incident: Incident, history: list[Incident]) -> dict:
        if not self.should_run(incident):
            return self.skipped_fields()
        try:
            return self.run(incident, history)
        except Exception as error:
            logger.warning("%s failed: %s", self.name, error)
            return self.error_fields(str(error))