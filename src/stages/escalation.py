"""
escalation.py — Stage 3: Escalation Detection.

This handler runs as a pre-filter BEFORE any stage-specific logic.
It uses a dedicated, lightweight LLM call focused purely on safety classification.

Design decision: separating escalation detection into its own LLM call (rather than
relying solely on the FAQ/Qualification prompt's escalation section) provides a
defence-in-depth approach. The classifier prompt is shorter and more focused,
reducing the risk of the model "reasoning around" an escalation trigger.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.models.schemas import (
    ConversationState,
    EscalationEvent,
    EscalationType,
    StageOutput,
)
from src.prompts.system import build_escalation_check_prompt
from src.utils.llm_client import BaseLLMClient
from src.utils.logger import EventLogger

logger = logging.getLogger(__name__)


class EscalationDetector:
    """
    Runs a fast, focused escalation check on every incoming message.

    Returns an EscalationEvent if any trigger fires, else None.
    Also handles the auto-escalation rule for consecutive SOP gaps.
    """

    CONFIDENCE_THRESHOLD = 0.5   # below this → escalate due to low confidence
    MAX_UNANSWERED = 2           # consecutive SOP gaps before forced escalation

    def __init__(self, llm: BaseLLMClient, sop_data: Dict[str, Any]) -> None:
        self._llm = llm
        self._sop = sop_data
        self._system_prompt = build_escalation_check_prompt(sop_data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        state: ConversationState,
        user_message: str,
    ) -> Optional[EscalationEvent]:
        """
        Run escalation checks for the given message.

        Returns:
            EscalationEvent if escalation should occur, else None.
        """
        # Fast path: already escalated
        if state.escalation_log is not None:
            return state.escalation_log

        # Check 1: LLM-based trigger detection
        event = self._llm_check(state, user_message)
        if event:
            return event

        # Check 2: Consecutive unanswered SOP questions rule
        if state.unanswered_count >= self.MAX_UNANSWERED:
            logger.warning(
                "session=%s auto-escalating — %d consecutive SOP gaps",
                state.session_id,
                state.unanswered_count,
            )
            event = EscalationEvent(
                reason=f"AI could not answer {state.unanswered_count} consecutive questions from the SOP.",
                trigger_type=EscalationType.OUT_OF_SCOPE,
                confidence_score=1.0,
                flagged_message=user_message,
            )
            self._audit(state.session_id, event)
            return event

        return None

    def check_low_confidence(
        self,
        state: ConversationState,
        user_message: str,
        confidence: float,
    ) -> Optional[EscalationEvent]:
        """
        Secondary check called by stage handlers after getting the LLM response.
        Escalates if model confidence falls below threshold.
        """
        if confidence < self.CONFIDENCE_THRESHOLD:
            logger.warning(
                "session=%s low confidence=%.2f — escalating",
                state.session_id,
                confidence,
            )
            event = EscalationEvent(
                reason=f"Model confidence too low ({confidence:.0%}) to answer reliably.",
                trigger_type=EscalationType.LOW_CONFIDENCE,
                confidence_score=confidence,
                flagged_message=user_message,
            )
            self._audit(state.session_id, event)
            return event
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _llm_check(
        self,
        state: ConversationState,
        user_message: str,
    ) -> Optional[EscalationEvent]:
        """Run the LLM-based escalation classifier."""
        try:
            result = self._llm.complete_json(
                system=self._system_prompt,
                messages=[{"role": "user", "content": user_message}],
                max_tokens=256,
                temperature=0.0,  # deterministic classification
            )
        except Exception as exc:
            logger.error("Escalation LLM call failed: %s — defaulting to no-escalate", exc)
            return None

        if not result.get("escalate", False):
            return None

        try:
            trigger_type = EscalationType(result.get("escalation_type", "out_of_scope"))
        except ValueError:
            trigger_type = EscalationType.OUT_OF_SCOPE

        event = EscalationEvent(
            reason=result.get("escalation_reason", "Escalation trigger detected."),
            trigger_type=trigger_type,
            confidence_score=float(result.get("confidence", 1.0)),
            flagged_message=user_message,
        )
        self._audit(state.session_id, event)
        return event

    @staticmethod
    def _audit(session_id: str, event: EscalationEvent) -> None:
        EventLogger.log_escalation(
            session_id=session_id,
            trigger_type=event.trigger_type.value,
            reason=event.reason,
            confidence=event.confidence_score,
            flagged_message=event.flagged_message,
        )
        logger.warning(
            "ESCALATION | session=%s type=%s reason=%s",
            session_id,
            event.trigger_type.value,
            event.reason,
        )
