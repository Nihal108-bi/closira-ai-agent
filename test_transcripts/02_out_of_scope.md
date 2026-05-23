# Test Transcript 2 — Out-of-Scope Question

**Scenario:** Customer asks about services not listed in the SOP (laser hair removal, skin peels). The AI must acknowledge the gap honestly and escalate rather than guessing.

**Expected behaviour:** `sop_gap_detected=true`, honest acknowledgement, escalation offer. NO invented services or pricing.

---

**Session ID:** `demo-02`  
**Stage:** FAQ → ESCALATED

---

```
Bloom 🌸: Hello! Welcome to Bloom Aesthetics Clinic. I'm Bloom, your AI assistant.
           How can I help you today?

Customer:  Hello, do you offer laser hair removal?

Bloom 🌸: That's a great question! I want to make sure I give you accurate information —
           laser hair removal isn't something I have details on in our current service
           information.

           To make sure you get the right answer, I'd love to connect you with one of
           our clinic coordinators who can confirm exactly what we offer.

           Is there anything else I can help with in the meantime, or shall I flag
           this for the team?

Customer:  What about skin peels?

Bloom 🌸: I'm connecting you with one of our clinic coordinators who will be able to
           help you directly. A team member will be in touch shortly. 💙
```

---

**Escalation log entry (from `logs/events.jsonl`):**

```json
{
  "ts": "2025-01-15T14:45:02Z",
  "event_type": "ESCALATION",
  "session_id": "demo-02",
  "trigger_type": "out_of_scope",
  "reason": "AI could not answer 2 consecutive questions from the SOP.",
  "confidence": 1.0,
  "flagged_message": "What about skin peels?"
}
```

---

**Evaluation Notes:**

| Check | Result |
|---|---|
| AI did NOT invent laser hair removal pricing | ✅ |
| AI did NOT invent skin peel details | ✅ |
| SOP gap acknowledged honestly on first question | ✅ |
| Automatic escalation triggered after 2nd unanswered question | ✅ |
| Escalation reason logged correctly (`out_of_scope`) | ✅ |
| Handoff message warm and professional | ✅ |
| `sop_gap_detected` (turn 1) | `true` |
| `sop_gap_detected` (turn 2) | `true` — triggers auto-escalation |
| `confidence` | `0.1` |
