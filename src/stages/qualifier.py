"""
qualifier.py — Stage 2: Lead Qualification.

Asks 3 structured questions one-at-a-time to collect lead data.
Extracted answers are stored in ConversationState.lead_data for downstream use.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.models.schemas import ConversationState, LeadData, StageOutput
from src.prompts.system import build_qualification_prompt
from src.utils.llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

# Maps qualification step index → LeadData field name
_STEP_TO_FIELD = {
    0: "treatment_interest",
    1: "prior_experience",
    2: "goals_or_concerns",
}

TOTAL_QUESTIONS = 3


class LeadQualifier:
    """
    Runs the 3-question lead qualification flow.

    Each call to handle() advances the conversation by one question.
    Extracted answers are written directly into state.lead_data.
    """

    def __init__(self, llm: BaseLLMClient, sop_data: Dict[str, Any]) -> None:
        self._llm = llm
        self._sop = sop_data

    def handle(
        self,
        state: ConversationState,
        user_message: str,
    ) -> StageOutput:
        """
        Process one turn of the qualification flow.

        Returns StageOutput with stage_complete=True on the final step.
        """
        step = state.qualification_step
        logger.info(
            "session=%s Qualification handler | step=%d/%d",
            state.session_id,
            step + 1,
            TOTAL_QUESTIONS,
        )

        system = build_qualification_prompt(self._sop, step)
        history = state.get_llm_history()[-10:]

        try:
            raw = self._llm.complete_json(
                system=system,
                messages=history,
                max_tokens=512,
                temperature=0.1,
            )
        except Exception as exc:
            logger.error("Qualification LLM call failed: %s", exc)
            return self._fallback_response()

        output = self._parse_output(raw, state, user_message, step)
        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_output(
        self,
        raw: Dict[str, Any],
        state: ConversationState,
        user_message: str,
        step: int,
    ) -> StageOutput:
        """Parse LLM output, store extracted data, and advance the step counter."""
        extracted = raw.get("extracted_data", {})

        # Store the answer for the current step
        field = _STEP_TO_FIELD.get(step)
        if field and extracted:
            # Try common key variants the LLM might use
            value = (
                extracted.get(field)
                or extracted.get("answer")
                or extracted.get("response")
                or next(iter(extracted.values()), None)
            )
            if value:
                setattr(state.lead_data, field, str(value))
                logger.debug(
                    "session=%s extracted %s=%r", state.session_id, field, value
                )

        stage_complete = raw.get("stage_complete", False)

        # Advance step if there are more questions AND the model hasn't signalled completion
        if not stage_complete and step < TOTAL_QUESTIONS - 1:
            state.qualification_step += 1
        elif stage_complete or step >= TOTAL_QUESTIONS - 1:
            # Force completion on last step regardless
            stage_complete = True

        logger.debug(
            "session=%s qualification step=%d -> %d stage_complete=%s",
            state.session_id,
            step,
            state.qualification_step,
            stage_complete,
        )

        return StageOutput(
            response=raw.get("response", "Thank you! Let me note that down."),
            confidence=float(raw.get("confidence", 1.0)),
            escalate=raw.get("escalate", False),
            escalation_reason=raw.get("escalation_reason"),
            escalation_type=raw.get("escalation_type"),
            stage_complete=stage_complete,
            sop_gap_detected=raw.get("sop_gap_detected", False),
            sop_gap_description=raw.get("sop_gap_description"),
            extracted_data=extracted,
        )

    @staticmethod
    def _fallback_response() -> StageOutput:
        return StageOutput(
            response=(
                "I'm sorry, I hit a brief issue. "
                "Let me connect you with a team member who can continue from here."
            ),
            confidence=0.0,
            escalate=True,
            escalation_reason="Qualification LLM call failed.",
            escalation_type="out_of_scope",
            stage_complete=False,
        )
