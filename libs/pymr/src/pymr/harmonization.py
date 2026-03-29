from dataclasses import dataclass
from typing import Any

@dataclass
class HarmonizeInput:
    exposure_dat: Any
    outcome_dat: Any

def harmonize(input: HarmonizeInput):
    pass