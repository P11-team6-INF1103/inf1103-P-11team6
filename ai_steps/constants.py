#Ren Xiang

# Allowed values for the AI's structured output. What each value means for
# severity is decided in logic_manager.py, not here.
HAZARD_CATEGORIES = (
    "fall", "fall_from_height", "electrical", "chemical", "vehicular",
    "struck_by_machinery", "low_visibility", "other",
)

INJURY_TREATMENTS = ("none", "first_aid", "hospital", "died", "unspecified")

PPE_VALUES = ("worn", "not_worn", "unspecified")