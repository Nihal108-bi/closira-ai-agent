"""
faq.py — Stage 1: FAQ Answering.

Handles all inbound customer questions by grounding responses strictly in the SOP.
Tracks SOP gaps and determines when to transition to the Qualification stage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.models.schemas import ConversationState, StageOutput
from src.prompts.system import build_faq_prompt
from src.utils.llm_client import BaseLLMClient
from src.utils.logger import EventLogger

logger = logging.getLogger(__name__)

# Minimum confidence to answer without flagging a gap
_CONFIDENCE_FLOOR = 0.6


class FAQHandler:
    """
    Answers customer questions using only the provided SOP data.

    Key responsibilities:
    - SOP-grounded answers only (enforced at prompt level + confidence check)
    - Tracks consecutive unanswered questions on the state
    - Signals stage_complete when the customer is ready for qualification
    """

    def __init__(self, llm: BaseLLMClient, sop_data: Dict[str, Any]) -> None:
        self._llm = llm
        self._sop = sop_data
        self._system_prompt = build_faq_prompt(sop_data)

    def handle(
        self,
        state: ConversationState,
        user_message: str,
    ) -> StageOutput:
        """
        Process a user message in the FAQ stage.

        Returns a StageOutput with the customer-facing response and metadata.
        """
        logger.info("session=%s FAQ handler processing message", state.session_id)

        # Build message history for context (last 10 turns to stay within token budget)
        history = state.get_llm_history()[-10:]

        try:
            raw = self._llm.complete_json(
                system=self._system_prompt,
                messages=history,
                max_tokens=512,
                temperature=0.1,
            )
        except Exception as exc:
            logger.error("FAQ LLM call failed: %s", exc)
            return self._fallback_response(user_message)

        output = self._parse_output(raw, state, user_message)
        logger.debug(
            "session=%s FAQ output | confidence=%.2f stage_complete=%s sop_gap=%s",
            state.session_id,
            output.confidence,
            output.stage_complete,
            output.sop_gap_detected,
        )
        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_output(
        self,
        raw: Dict[str, Any],
        state: ConversationState,
        user_message: str,
    ) -> StageOutput:
        """Convert raw LLM dict into a validated StageOutput and update state."""
        confidence = float(raw.get("confidence", 1.0))
        sop_gap = raw.get("sop_gap_detected", False)
        gap_description = raw.get("sop_gap_description")

        # Update consecutive unanswered counter
        if sop_gap or confidence < _CONFIDENCE_FLOOR:
            state.unanswered_count += 1
            if gap_description:
                state.sop_gaps.append(gap_description)
                EventLogger.log_sop_gap(state.session_id, gap_description)
                logger.info(
                    "session=%s SOP gap detected: %s", state.session_id, gap_description
                )
        else:
            # Reset counter on a successful answer
            state.unanswered_count = 0

        return StageOutput(
            response=raw.get("response", "I'm sorry, I didn't understand that. Could you rephrase?"),
            confidence=confidence,
            escalate=raw.get("escalate", False),
            escalation_reason=raw.get("escalation_reason"),
            escalation_type=raw.get("escalation_type"),
            stage_complete=raw.get("stage_complete", False),
            sop_gap_detected=sop_gap,
            sop_gap_description=gap_description,
            extracted_data=raw.get("extracted_data", {}),
        )

    @staticmethod
    def _fallback_response(user_message: str) -> StageOutput:
        """Safe fallback when the LLM call itself fails."""
        return StageOutput(
            response=(
                "I'm experiencing a brief technical hiccup. "
                "Could you hold on a moment? I'll connect you with a team member right away."
            ),
            confidence=0.0,
            escalate=True,
            escalation_reason="LLM call failed — automatic fallback escalation.",
            escalation_type="out_of_scope",
            stage_complete=False,
        )
