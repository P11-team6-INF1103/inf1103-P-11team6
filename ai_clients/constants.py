# Ren Xiang
# Fixed seed so the same input gives the same answer as far as the model allows.
AI_SEED = 42

# Lennart
# Filler words ignored when comparing descriptions. Negations ("not", "no") stay in: they change the meaning.
FILLER_WORDS = frozenset({
    "a", "an", "the", "and", "was", "were", "is", "are", "be", "been", "being",
    "this", "that", "these", "those", "his", "her", "their", "its",
})
# A spelling slip is forgiven only in long words with the same first and last letter.
TYPO_MIN_LENGTH = 6
TYPO_MIN_RATIO = 0.9
# Saved descriptions kept per kind of request; the oldest is dropped first.
MAX_SIMILAR_PER_SCOPE = 200
