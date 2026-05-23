"""
summarizer.py — Stage 4: Conversation Summary.

Generates a structured end-of-session summary from the full conversation transcript.
The summary is both returned to the CLI and persisted to the audit log.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from src.models.schemas import ConversationState, ConversationSummary
from src.prompts.system import build_summary_prompt
from src.utils.llm_client import BaseLLMClient
from src.utils.logger import EventLogger

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """
    Produces a structured ConversationSummary from the session state and transcript.

    The full conversation history is passed as a single formatted document so the
    LLM has complete context to extract intent, gaps, and next actions.
    """

    def __init__(self, llm: BaseLLMClient, sop_data: Dict[str, Any]) -> None:
        self._llm = llm
        self._sop = sop_data
        self._system_prompt = build_summary_prompt(sop_data)

    def generate(self, state: ConversationState) -> ConversationSummary:
        """
        Analyse the conversation and return a ConversationSummary.
        Also persists the session end event to the audit log.
        """
        logger.info("session=%s generating conversation summary", state.session_id)

        transcript = self._format_transcript(state)

        try:
            raw = self._llm.complete_json(
                system=self._system_prompt,
                messages=[{"role": "user", "content": transcript}],
                max_tokens=768,
                temperature=0.0,
            )
        except Exception as exc:
            logger.error("Summary LLM call failed: %s", exc)
            raw = self._fallback_raw(state)

        summary = self._build_summary(raw, state)

        EventLogger.log_session_end(
            session_id=state.session_id,
            stage_reached=state.stage.value,
            turns=len([m for m in state.messages if m.role.value == "user"]),
        )
        logger.info("session=%s summary generated", state.session_id)
        return summary

    def format_for_display(self, summary: ConversationSummary) -> str:
        """
        Render the summary as a human-readable string for CLI output.
        Also works without Rich for plain-text environments.
        """
        lines = [
            "─" * 60,
            f"  SESSION SUMMARY  •  ID: {summary.session_id}",
            "─" * 60,
            f"  Customer Intent    : {summary.customer_intent}",
            f"  Stage Reached      : {summary.stage_reached.value.upper()}",
            f"  Session Duration   : {summary.duration_seconds:.0f}s",
            f"  Total Turns        : {summary.total_turns}",
            "",
            "  Lead Data Collected:",
            f"    Treatment Interest : {summary.lead_data.treatment_interest or '—'}",
            f"    Prior Experience   : {summary.lead_data.prior_experience or '—'}",
            f"    Goals / Concerns   : {summary.lead_data.goals_or_concerns or '—'}",
        ]

        if summary.sop_gaps:
            lines += ["", "  SOP Gaps Identified:"]
            for gap in summary.sop_gaps:
                lines.append(f"    • {gap}")
        else:
            lines.append("  SOP Gaps Identified : None")

        if summary.escalation_event:
            lines += [
                "",
                "  ⚠  ESCALATION OCCURRED",
                f"    Type   : {summary.escalation_event.trigger_type.value}",
                f"    Reason : {summary.escalation_event.reason}",
            ]

        lines += [
            "",
            f"  Recommended Next Action:",
            f"    {summary.recommended_next_action}",
            "─" * 60,
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_transcript(state: ConversationState) -> str:
        """Format the conversation history as a numbered transcript string."""
        lines = ["CONVERSATION TRANSCRIPT", "=" * 40]
        for i, msg in enumerate(state.messages, 1):
            role = "CUSTOMER" if msg.role.value == "user" else "BLOOM (AI)"
            lines.append(f"[{i}] {role}: {msg.content}")
        lines += [
            "=" * 40,
            f"Session ID: {state.session_id}",
            f"Stage reached: {state.stage.value}",
            f"SOP gaps flagged: {json.dumps(state.sop_gaps)}",
            f"Escalation: {'YES — ' + state.escalation_log.reason if state.escalation_log else 'NO'}",
        ]
        return "\n".join(lines)

    def _build_summary(
        self, raw: Dict[str, Any], state: ConversationState
    ) -> ConversationSummary:
        """Merge LLM extraction with known state data into a ConversationSummary."""
        # Merge LLM-extracted lead details with already-collected state data
        key_details = raw.get("key_details", {})
        lead = LeadDataMerger.merge(state.lead_data, key_details)

        # Merge SOP gaps from state + any new ones the LLM found
        all_gaps = list(
            dict.fromkeys(state.sop_gaps + raw.get("sop_gaps", []))
        )

        user_turns = [m for m in state.messages if m.role.value == "user"]

        return ConversationSummary(
            session_id=state.session_id,
            customer_intent=raw.get("customer_intent", "Intent unclear."),
            stage_reached=state.stage,
            lead_data=lead,
            sop_gaps=all_gaps,
            escalation_event=state.escalation_log,
            recommended_next_action=raw.get(
                "recommended_next_action",
                "Review conversation and follow up within 24 hours.",
            ),
            total_turns=len(user_turns),
            duration_seconds=state.session_duration_seconds(),
        )

    @staticmethod
    def _fallback_raw(state: ConversationState) -> Dict[str, Any]:
        return {
            "customer_intent": "Could not determine — summary generation failed.",
            "key_details": {},
            "sop_gaps": state.sop_gaps,
            "escalation_occurred": state.escalation_log is not None,
            "escalation_reason": state.escalation_log.reason if state.escalation_log else None,
            "recommended_next_action": "Manual review required — summary generation failed.",
            "overall_sentiment": "neutral",
        }


class LeadDataMerger:
    """Utility to merge LLM-extracted key details with state.lead_data."""

    @staticmethod
    def merge(existing: "LeadData", extracted: Dict[str, Any]) -> "LeadData":
        from src.models.schemas import LeadData
        return LeadData(
            treatment_interest=existing.treatment_interest or extracted.get("treatment_interest"),
            prior_experience=existing.prior_experience or extracted.get("prior_experience"),
            goals_or_concerns=existing.goals_or_concerns or extracted.get("goals_or_concerns"),
            contact_name=existing.contact_name,
            additional_info=existing.additional_info,
        )
