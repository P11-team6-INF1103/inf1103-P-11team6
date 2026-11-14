# Ren Xiang
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
from ai_steps.hazard_flag_step import HazardFlagStep
from ai_steps.photo_analysis_step import PhotoAnalysisStep
from ai_steps.review_step import ReviewStep
from ai_steps.similar_incident_step import SimilarIncidentStep
from tests.fakes import HAZARD_REPLY, PHOTO_REPLY, REVIEW_REPLY


class FakeGemini:
    # Stands in for GeminiClient: same ask_json() method, answers picked by which schema is asked for.
    def __init__(self, replies: dict | None = None, error: Exception | None = None) -> None:
        self.replies = {
            id(HazardFlagStep.SCHEMA): HAZARD_REPLY,
            id(PhotoAnalysisStep.SCHEMA): PHOTO_REPLY,
            id(ReviewStep.SCHEMA): REVIEW_REPLY,
            id(SimilarIncidentStep.SCHEMA): [],
        }
        self.replies.update(replies or {})
        self.error = error
        self.calls = []

    def ask_json(self, prompt: str, schema: dict, photo: object = None, subject: str | None = None) -> object:
        self.calls.append({"prompt": prompt, "schema": schema, "photo": photo, "subject": subject})
        if self.error:
            raise self.error
        return self.replies[id(schema)]