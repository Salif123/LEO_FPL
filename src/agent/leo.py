import os
from typing import Optional, Tuple
from config import GEMINI_API_KEY, MODEL_NAME
from src.engine.models import EngineVerdict, VerdictEnum
from src.agent.prompts import LEO_SYSTEM_PROMPT
from src.agent.validator import OutputValidator

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

class LeoAgent:
    """Leo the PL Lion - Grounded FPL Analyst Agent."""
    def __init__(self, api_key: Optional[str] = None, model_name: str = MODEL_NAME):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client = None
        if HAS_GENAI and self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Could not initialize Gemini client: {e}")

    def generate_explanation(self, verdict: EngineVerdict, user_query: str = "") -> str:
        """Generates Leo's grounded explanation using Gemini or the deterministic fallback synthesizer."""
        xml_packet = verdict.to_xml_data_packet()

        # If Gemini client is active, use LLM
        if self.client:
            try:
                return self._invoke_gemini_with_retries(xml_packet, verdict, user_query)
            except Exception as e:
                print(f"Gemini API invocation error: {e}. Using deterministic fallback synthesis.")

        # Deterministic fallback synthesizer
        return self._deterministic_synthesis(verdict)

    def _invoke_gemini_with_retries(self, xml_packet: str, verdict: EngineVerdict, user_query: str) -> str:
        prompt = f"""User asked: "{user_query or 'Analyze this player'}"

<data>
{xml_packet}
</data>

Explain the verdict in your voice following all absolute rules and the exact output format."""

        for attempt in range(2):
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=LEO_SYSTEM_PROMPT,
                    temperature=0.3,
                )
            )
            text = response.text.strip()
            is_valid, violations = OutputValidator.validate(text, verdict)
            if is_valid:
                return text
            
            # Add feedback for correction on second attempt
            prompt += f"\n\nCorrection needed: Your previous attempt had issues: {'; '.join(violations)}. Please fix and regenerate within 180 words."

        return text

    def _deterministic_synthesis(self, verdict: EngineVerdict) -> str:
        """Generates high-precision grounded Leo response adhering strictly to the template."""
        v_str = verdict.verdict.value
        p = verdict.target_player
        rep = verdict.recommended_replacement

        # Fixtures formatting
        fix_strs = [f.formatted for f in verdict.fixtures_cited[:2]]
        fixtures_text = " and ".join(fix_strs) if fix_strs else "Upcoming schedule as listed"

        # Construct Sections
        if verdict.verdict == VerdictEnum.TRANSFER_OUT and rep:
            why = f"{verdict.why_facts[0]}. {verdict.why_facts[1] if len(verdict.why_facts) > 1 else ''} {rep.web_name} boasts a form of {rep.form:.1f} and composite rating of {rep.composite_score:.1f}."
            move = f"{p.web_name} (£{verdict.selling_price:.1f}m) ➡️ {rep.web_name} (£{verdict.buy_price:.1f}m), resulting in £{verdict.bank_after:.1f}m in the bank."
        elif verdict.verdict == VerdictEnum.CAPTAIN:
            why = f"{verdict.why_facts[0]}. Facing {fixtures_text} gives {p.web_name} the prime ceiling this gameweek."
            move = f"Armband on {p.web_name} (£{p.price:.1f}m). Vice-captain on {rep.web_name if rep else 'backup'}."
        else:  # KEEP
            why = f"{verdict.why_facts[0]}. {verdict.why_facts[1] if len(verdict.why_facts) > 1 else ''} Holding through the swing preserves free transfers."
            move = "no move"

        risk = verdict.risk or "Fixture rotation or unexpected tactical blanks remain a possibility."

        response = f"""**VERDICT:** {v_str}

**WHY:** {why}

**THE FIXTURES:** {fixtures_text}.

**THE MOVE:** {move}

**RISK:** {risk}"""
        return response
