#Ren Xiang

from dataclasses import dataclass


@dataclass
class Result:
    status: str  # PASS, FAIL or SKIP
    detail: str = ""
    seconds: float = 0.0