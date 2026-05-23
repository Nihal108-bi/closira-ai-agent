# Test Transcript 3 — Escalation Trigger (Negative Sentiment / Complaint)

**Scenario:** Customer expresses strong dissatisfaction about a previous treatment. This is a complaint — an explicit escalation trigger in the SOP. The AI must detect the sentiment immediately and hand off without attempting to resolve the complaint itself.

**Expected behaviour:** Immediate escalation on the first message. No attempt to answer or defend. Warm, empathetic handoff message. Escalation type: `sentiment`.

---

**Session ID:** `demo-03`  
**Stage:** FAQ → ESCALATED (immediate)

---

```
Bloom 🌸: Hello! Welcome to Bloom Aesthetics Clinic. I'm Bloom, your AI assistant.
           How can I help you today?

Customer:  I'm really unhappy with my last treatment here. It was absolutely terrible
           and I want someone to explain what went wrong.

Bloom 🌸: I'm connecting you with one of our clinic coordinators who will be able to
           help you directly. A team member will be in touch shortly. 💙
```

---

**Escalation log entry (from `logs/events.jsonl`):**

```json
{
  "ts": "2025-01-15T15:02:14Z",
  "event_type": "ESCALATION",
  "session_id": "demo-03",
  "trigger_type": "sentiment",
  "reason": "Customer expressed strong dissatisfaction about a previous treatment — explicit complaint.",
  "confidence": 0.97,
  "flagged_message": "I'm really unhappy with my last treatment here. It was absolutely terrible and I want someone to explain what went wrong."
}
```

---

**Additional escalation test — Pricing Negotiation:**

```
Customer:  Can you do the Botox for £150? I've seen it cheaper elsewhere.

Bloom 🌸: I'm connecting you with one of our clinic coordinators who will be able to
           help you directly. A team member will be in touch shortly. 💙
```

```json
{
  "event_type": "ESCALATION",
  "trigger_type": "pricing_negotiation",
  "reason": "Customer requesting a discount on Botox — pricing negotiation detected.",
  "confidence": 0.99
}
```

---

**Additional escalation test — Medical Question:**

```
Customer:  I'm on blood thinners — is it safe for me to have Botox?

Bloom 🌸: I'm connecting you with one of our clinic coordinators who will be able to
           help you directly. A team member will be in touch shortly. 💙
```

```json
{
  "event_type": "ESCALATION",
  "trigger_type": "medical_question",
  "reason": "Customer asked about Botox safety with blood-thinning medication — medical question, requires clinical advice.",
  "confidence": 0.99
}
```

---

**Evaluation Notes:**

| Check | Result |
|---|---|
| Complaint → immediate escalation (no attempt to resolve) | ✅ |
| Escalation type correctly identified as `sentiment` | ✅ |
| Pricing negotiation → immediate escalation | ✅ |
| Medical question → immediate escalation | ✅ |
| AI did NOT attempt to answer medical question | ✅ |
| Handoff message consistent and warm across all trigger types | ✅ |
| All escalation events persisted to audit log | ✅ |
| Escalation happens on the SAME turn as the trigger (no delay) | ✅ |
