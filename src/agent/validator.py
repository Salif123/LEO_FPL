import re
from typing import Tuple, List
from src.engine.models import EngineVerdict

class OutputValidator:
    """Validates Leo's response against absolute rules."""
    
    @staticmethod
    def validate(response_text: str, verdict: EngineVerdict) -> Tuple[bool, List[str]]:
        violations = []
        words = response_text.split()
        word_count = len(words)

        # 1. Word count rule (Max 180 words)
        if word_count > 185:  # Slight grace margin for formatting tokens
            violations.append(f"Word count ({word_count}) exceeds the maximum 180 words limit.")

        # 2. Required section headers
        required_headers = ["**VERDICT:**", "**WHY:**", "**THE FIXTURES:**", "**THE MOVE:**", "**RISK:**"]
        for header in required_headers:
            if header.lower() not in response_text.lower():
                violations.append(f"Missing required section: {header}")

        # 3. Verdict alignment rule
        expected_verdict_str = verdict.verdict.value
        if expected_verdict_str not in response_text:
            violations.append(f"Verdict mismatch: Output does not state the expected '{expected_verdict_str}'.")

        # 4. Fixture citations check (at least 2 fixtures cited with H/A)
        # Look for patterns like (H, FDR 2) or (A, FDR 3) or SOU (H)
        fixture_matches = re.findall(r"\([HA],\s*FDR\s*\d\)", response_text, re.IGNORECASE)
        if len(fixture_matches) < 2:
            # Fallback looser check for (H) / (A) and FDR
            ha_matches = re.findall(r"\([HA]\)", response_text, re.IGNORECASE)
            fdr_matches = re.findall(r"FDR\s*\d", response_text, re.IGNORECASE)
            if not (len(ha_matches) >= 2 or len(fdr_matches) >= 2):
                violations.append("Did not clearly cite at least two upcoming fixtures with Home/Away and FDR difficulty.")

        is_valid = len(violations) == 0
        return is_valid, violations
