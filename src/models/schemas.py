"""
schemas.py — Core data models for the Closira AI Agent.
All state, events, and API structures are defined here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ConversationStage(str, Enum):
    """The four sequential processing stages of a Closira conversation."""
    FAQ = "faq"
    QUALIFICATION = "qualification"
    ESCALATED = "escalated"
    SUMMARY = "summary"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class EscalationType(str, Enum):
    SENTIMENT = "sentiment"
    OUT_OF_SCOPE = "out_of_scope"
    LOW_CONFIDENCE = "low_confidence"
    MEDICAL_QUESTION = "medical_question"
    PRICING_NEGOTIATION = "pricing_negotiation"
    EXPLICIT_REQUEST = "explicit_request"
    SAFETY_CONCERN = "safety_concern"


# ---------------------------------------------------------------------------
# Core message & state models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A single turn in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_llm_dict(self) -> Dict[str, str]:
        """Convert to the format expected by LLM APIs."""
        return {"role": self.role.value, "content": self.content}


class EscalationEvent(BaseModel):
    """Structured log entry for every escalation that occurs."""
    reason: str
    trigger_type: EscalationType
    confidence_score: float
    triggered_at: datetime = Field(default_factory=datetime.now)
    flagged_message: str


class LeadData(BaseModel):
    """Structured container for qualification answers collected from the customer."""
    treatment_interest: Optional[str] = None
    prior_experience: Optional[str] = None
    goals_or_concerns: Optional[str] = None
    contact_name: Optional[str] = None
    additional_info: Dict[str, Any] = Field(default_factory=dict)


class ConversationState(BaseModel):
    """
    The complete, serialisable state of one customer session.
    Passed between every handler — no global state.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    stage: ConversationStage = ConversationStage.FAQ
    messages: List[Message] = Field(default_factory=list)
    lead_data: LeadData = Field(default_factory=LeadData)
    escalation_log: Optional[EscalationEvent] = None
    sop_gaps: List[str] = Field(default_factory=list)
    unanswered_count: int = 0           # tracks consecutive SOP misses for auto-escalation
    qualification_step: int = 0         # which qualification question we're on (0-based)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role=MessageRole.USER, content=content))
        self.updated_at = datetime.now()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role=MessageRole.ASSISTANT, content=content))
        self.updated_at = datetime.now()

    def get_llm_history(self) -> List[Dict[str, str]]:
        """Return the conversation history in LLM-ready format (excludes system messages)."""
        return [
            m.to_llm_dict()
            for m in self.messages
            if m.role != MessageRole.SYSTEM
        ]

    def session_duration_seconds(self) -> float:
        return (self.updated_at - self.created_at).total_seconds()


# ---------------------------------------------------------------------------
# LLM structured output model
# ---------------------------------------------------------------------------

class StageOutput(BaseModel):
    """
    The structured JSON output expected from the LLM on every call.
    Every stage handler parses the LLM response into this model.
    """
    response: str                                  # customer-facing message
    confidence: float = Field(ge=0.0, le=1.0)
    escalate: bool = False
    escalation_reason: Optional[str] = None
    escalation_type: Optional[str] = None
    stage_complete: bool = False
    sop_gap_detected: bool = False
    sop_gap_description: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Final summary model
# ---------------------------------------------------------------------------

class ConversationSummary(BaseModel):
    """Structured end-of-session summary produced by the Summarizer stage."""
    session_id: str
    customer_intent: str
    stage_reached: ConversationStage
    lead_data: LeadData
    sop_gaps: List[str]
    escalation_event: Optional[EscalationEvent]
    recommended_next_action: str
    total_turns: int
    duration_seconds: float
