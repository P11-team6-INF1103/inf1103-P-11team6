import logging
from concurrent.futures import ThreadPoolExecutor

from ai_clients.gemini_client import GeminiClient
from ai_clients.groq_search_client import GroqSearchClient
from ai_clients.weather_client import WeatherClient
from ai_steps.hazard_flag_step import HazardFlagStep
from ai_steps.photo_analysis_step import PhotoAnalysisStep
from ai_steps.review_step import ReviewStep
from ai_steps.similar_incident_step import SimilarIncidentStep
from ai_steps.site_plan_reader import SitePlanReader
from ai_steps.weather_step import WeatherStep
from ai_steps.web_search_step import WebSearchStep
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from site_plan.site_plan import SitePlan

logger = logging.getLogger(__name__)

#Ren Xiang
class AIManager:
    # Creates and owns its steps (composition); the clients are shared and passed in (association).
    def __init__(self, gemini: GeminiClient, search: GroqSearchClient, weather: WeatherClient,
                 outcome_meanings: dict) -> None:
        self._hazard_step = HazardFlagStep(gemini)
        self._evidence_steps = [
            PhotoAnalysisStep(gemini),
            WeatherStep(weather),
            SimilarIncidentStep(gemini, outcome_meanings),
            WebSearchStep(search),
        ]
        self._review_step = ReviewStep(gemini)
        self._plan_reader = SitePlanReader(gemini)

    # Step 1: the hazard facts, which decide whether the incident is real at all.
    def extract_hazards(self, incident: Incident) -> None:
        incident.update(self._hazard_step.safe_run(incident, []))

    # Step 2: the evidence steps read different inputs and none needs another's result,
    # so they run at the same time in worker threads (advanced feature: threading).
    def gather_evidence(self, incident: Incident, history: list[Incident]) -> None:
        with ThreadPoolExecutor(max_workers=len(self._evidence_steps)) as pool:
            futures = [pool.submit(step.safe_run, incident, history) for step in self._evidence_steps]
            results = [future.result() for future in futures]
        for fields in results:
            incident.update(fields)

    # Step 3: the after-action review, last because it reads everything else.
    def write_review(self, incident: Incident) -> None:
        incident.update(self._review_step.safe_run(incident, []))

    # The site plan feature: reads a plan image into a draft SitePlan (not saved until the user confirms it).
    def read_site_plan(self, image: IncidentPhoto, width_m: float, aspect: float, name: str = "") -> SitePlan:
        return self._plan_reader.read(image, width_m, aspect, name)
