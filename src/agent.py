"""
agent.py — The Closira Agent Orchestrator.

This is the single entry point for processing a customer message.
It owns the conversation state machine and routes messages to the
correct stage handler.

State transitions:
  FAQ  ──(stage_complete)──► QUALIFICATION
  FAQ  ──(escalation)──────► ESCALATED
  QUALIFICATION ──(done)──► SUMMARY
  QUALIFICATION ──(esc.)──► ESCALATED
  Any ──(error)────────────► ESCALATED   (safe fallback)

No global state: ConversationState is passed in and returned on every call.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from src.models.schemas import (
    ConversationStage,
    ConversationState,
    ConversationSummary,
    EscalationEvent,
)
from src.stages.escalation import EscalationDetector
from src.stages.faq import FAQHandler
from src.stages.qualifier import LeadQualifier
from src.stages.summarizer import ConversationSummarizer
from src.utils.llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

# Customer-facing message when handing off to a human agent
_ESCALATION_MESSAGE = (
    "I'm connecting you with one of our clinic coordinators who will be able to "
    "help you directly. A team member will be in touch shortly. 💙"
)

# Shown after the session ends naturally
_SESSION_CLOSED_MESSAGE = (
    "Thank you for getting in touch with Bloom Aesthetics Clinic! "
    "Your session has ended. We look forward to welcoming you. 🌸"
)


class ClosiraAgent:
    """
    Orchestrates the four-stage Closira customer support workflow.

    Usage:
        agent = ClosiraAgent(llm_client, sop_data)
        state = ConversationState()
        response, state = agent.process(state, "Hello, what are your Botox prices?")
    """

    def __init__(self, llm: BaseLLMClient, sop_data: Dict[str, Any]) -> None:
        self._llm = llm
        self._sop = sop_data

        # Instantiate stage handlers once (they are stateless)
        self._faq = FAQHandler(llm, sop_data)
        self._qualifier = LeadQualifier(llm, sop_data)
        self._escalation_detector = EscalationDetector(llm, sop_data)
        self._summarizer = ConversationSummarizer(llm, sop_data)

        logger.info("ClosiraAgent initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        state: ConversationState,
        user_message: str,
    ) -> Tuple[str, ConversationState, ConversationSummary | None]:
        """
        Process one customer message and return the assistant's reply.

        Args:
            state: The current ConversationState (mutated in place).
            user_message: The raw text from the customer.

        Returns:
            (response_text, updated_state, summary_or_None)
            summary is only populated when the session reaches SUMMARY stage.
        """
        # 1. Record the user's message
        state.add_user_message(user_message)
        logger.info(
            "session=%s stage=%s processing message",
            state.session_id,
            state.stage.value,
        )

        summary: ConversationSummary | None = None

        # 2. If already escalated or summarised, short-circuit
        if state.stage == ConversationStage.ESCALATED:
            response = _ESCALATION_MESSAGE
            state.add_assistant_message(response)
            return response, state, summary

        if state.stage == ConversationStage.SUMMARY:
            response = _SESSION_CLOSED_MESSAGE
            state.add_assistant_message(response)
            return response, state, summary

        # 3. Escalation pre-filter (runs on every active message)
        escalation_event = self._escalation_detector.check(state, user_message)
        if escalation_event:
            state = self._apply_escalation(state, escalation_event)
            state.add_assistant_message(_ESCALATION_MESSAGE)
            return _ESCALATION_MESSAGE, state, summary

        # 4. Route to current stage handler
        try:
            response, state, summary = self._route(state, user_message)
        except Exception as exc:
            logger.exception("session=%s unhandled error in stage handler: %s", state.session_id, exc)
            escalation_event = EscalationEvent(
                reason=f"Internal error: {exc}",
                trigger_type="out_of_scope",  # type: ignore[arg-type]
                confidence_score=0.0,
                flagged_message=user_message,
            )
            state = self._apply_escalation(state, escalation_event)
            response = _ESCALATION_MESSAGE

        state.add_assistant_message(response)
        return response, state, summary

    def new_session(self) -> ConversationState:
        """Convenience factory — create a fresh ConversationState."""
        return ConversationState()

    # ------------------------------------------------------------------
    # Private routing
    # ------------------------------------------------------------------

    def _route(
        self,
        state: ConversationState,
        user_message: str,
    ) -> Tuple[str, ConversationState, ConversationSummary | None]:
        """Dispatch to the correct stage handler and handle transitions."""
        summary = None

        if state.stage == ConversationStage.FAQ:
            output = self._faq.handle(state, user_message)

            # Stage handler may also detect escalation
            if output.escalate:
                event = EscalationEvent(
                    reason=output.escalation_reason or "Escalation flagged by FAQ handler.",
                    trigger_type=output.escalation_type or "out_of_scope",  # type: ignore[arg-type]
                    confidence_score=output.confidence,
                    flagged_message=user_message,
                )
                state = self._apply_escalation(state, event)
                return _ESCALATION_MESSAGE, state, summary

            # Check confidence threshold
            conf_event = self._escalation_detector.check_low_confidence(
                state, user_message, output.confidence
            )
            if conf_event:
                state = self._apply_escalation(state, conf_event)
                return _ESCALATION_MESSAGE, state, summary

            # Transition to QUALIFICATION when FAQ stage signals completion
            if output.stage_complete:
                state.stage = ConversationStage.QUALIFICATION
                logger.info("session=%s → QUALIFICATION", state.session_id)

            return output.response, state, summary

        if state.stage == ConversationStage.QUALIFICATION:
            output = self._qualifier.handle(state, user_message)

            if output.escalate:
                event = EscalationEvent(
                    reason=output.escalation_reason or "Escalation flagged by Qualifier.",
                    trigger_type=output.escalation_type or "out_of_scope",  # type: ignore[arg-type]
                    confidence_score=output.confidence,
                    flagged_message=user_message,
                )
                state = self._apply_escalation(state, event)
                return _ESCALATION_MESSAGE, state, summary

            # All qualification questions answered → generate summary
            if output.stage_complete:
                state.stage = ConversationStage.SUMMARY
                logger.info("session=%s → SUMMARY", state.session_id)
                summary = self._summarizer.generate(state)
                summary_display = self._summarizer.format_for_display(summary)
                combined_response = (
                    f"{output.response}\n\n"
                    f"That's everything I needed! Here's a quick summary of your session:\n\n"
                    f"```\n{summary_display}\n```"
                )
                return combined_response, state, summary

            return output.response, state, summary

        # Fallback for unexpected states
        logger.error("session=%s unexpected stage=%s", state.session_id, state.stage)
        return "Something unexpected happened. Let me connect you with the team.", state, summary

    @staticmethod
    def _apply_escalation(
        state: ConversationState,
        event: EscalationEvent,
    ) -> ConversationState:
        """Mark the state as escalated and persist the event."""
        state.stage = ConversationStage.ESCALATED
        state.escalation_log = event
        return state
