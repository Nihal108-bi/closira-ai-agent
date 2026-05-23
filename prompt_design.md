# Prompt Design Document — Closira AI Agent

> **Candidate:** Nihal Jaiswal  
> **Assignment:** AI Engineering Intern — Closira  
> **Model:** Claude 3.5 Haiku (Anthropic) · also compatible with GPT-4o-mini (OpenAI)

---

## 1. System Prompt — Full Text

Each stage has its own dedicated system prompt (see `src/prompts/system.py`). Below is the annotated FAQ stage prompt — the most comprehensive, as it handles the widest range of inputs.

```
You are Bloom, the AI customer communication assistant for Bloom Aesthetics Clinic in London.
You handle inbound enquiries via WhatsApp and digital channels with warmth and professionalism.

## YOUR IDENTITY
- Name: Bloom
- Persona: Friendly, reassuring, knowledgeable — like a premium clinic receptionist
- You are an AI. If directly asked whether you are human, be honest, but keep it brief.
- Never be cold or robotic. Use natural, conversational language.

## SOP — YOUR ONLY SOURCE OF TRUTH
You must answer EXCLUSIVELY from the data below. Never invent prices, services, or policies.

{sop_json injected at runtime}

## HALLUCINATION PREVENTION
- If the customer asks about something NOT in the SOP → set sop_gap_detected=true,
  acknowledge you don't have that information, and offer to escalate.
- Never fill gaps with guesses or general knowledge about aesthetics clinics.
- If unsure whether something is in the SOP → set confidence < 0.7 and be transparent.

## ESCALATION PRIORITY RULES
[... full escalation guard ...]

## REQUIRED OUTPUT FORMAT
Always respond with a single valid JSON object — no markdown, no prose outside the JSON.
[... full JSON schema ...]
```

---

## 2. Key Design Decisions

### 2.1 Separate prompt per stage

Rather than a single monolithic prompt with a stage switch, each of the four stages has its own focused system prompt. This reduces the risk of the model ignoring stage-specific rules when the prompt is long, and makes prompt iteration faster — changing the qualification prompt doesn't risk breaking the FAQ prompt.

### 2.2 SOP as runtime injection

The SOP JSON is loaded at startup and injected into every prompt at call time. This means:
- **No retraining required** to update business information.
- **The SOP is always the ground truth** — the model never relies on parametric knowledge for business facts.
- The SOP can be swapped out for any SMB without changing any code.

### 2.3 Structured JSON output (all stages)

Every LLM call returns a JSON object with a fixed schema. This is enforced by:
1. Explicitly showing the schema in the system prompt with descriptions for every field.
2. A robust `parse_json()` utility (`src/utils/llm_client.py`) that handles markdown code fences and leading prose in case the model adds them.
3. Setting `temperature=0.1` (or `0.0` for classifiers) to reduce format drift.

The alternative — free-text responses parsed with regex — is fragile and unreliable across providers.

### 2.4 Dual-provider abstraction

`BaseLLMClient` defines a common `complete()` interface. `AnthropicClient` and `OpenAIClient` implement it. The rest of the codebase has zero provider-specific code. Switching from Anthropic to OpenAI is a single CLI flag (`--provider openai`).

---

## 3. Hallucination Prevention

Four layers work together to prevent the model from inventing facts:

| Layer | Mechanism |
|---|---|
| **Prompt grounding** | SOP injected as the explicit source of truth. Model instructed: "Answer EXCLUSIVELY from the data below." |
| **Negative instruction** | "Never fill gaps with guesses or general knowledge about aesthetics clinics." |
| **Confidence scoring** | Model outputs `confidence` (0–1). Below 0.6, a SOP gap is flagged and logged. |
| **Gap counter** | `unanswered_count` tracks consecutive SOP misses. After 2, the next unanswered question triggers automatic escalation. |

**Why this works:** The model is incentivised to set `sop_gap_detected=true` rather than guess, because the prompt explicitly shows this as the correct behaviour when information is missing. Unlike asking the model to "only answer from the SOP" without structure, the JSON output schema gives the model a clear mechanism to express uncertainty without breaking the conversation.

---

## 4. Confidence-Based Escalation

Confidence is a first-class field in the output schema. The escalation logic has three tiers:

```
confidence >= 0.8   → Answer confidently
confidence 0.6–0.79 → Answer with transparency ("Based on what I have...")
confidence < 0.6    → Set sop_gap_detected=true
                      If consecutive gaps >= 2 → auto-escalate
```

Additionally, `EscalationDetector` runs a **separate, dedicated LLM call** on every message using a shorter, more focused prompt. This provides defence-in-depth: the main stage prompt may generate a response while the classifier simultaneously flags the message for escalation. The classifier uses `temperature=0.0` for maximum consistency.

This dual-check approach is intentional: a long, multi-task prompt is more likely to "reason around" an escalation trigger. A short, single-purpose classifier is harder to fool.

---

## 5. Tone & Persona Design

**Persona name:** Bloom (matching the clinic name — reinforces brand coherence)

**Target register:** Premium clinic receptionist — warm, reassuring, professional. Not clinical, not casual. Comparable to how a front desk person at a Harley Street clinic would speak.

**Specific instructions in the prompt:**
- Use natural, conversational language (not bullet points in chat)
- Acknowledge feelings before answering (especially for escalation messages)
- Avoid robotic phrasing like "I have located the following information"
- Emoji used sparingly and appropriately (💙 for escalation warmth, 🌸 for greeting)

**Why this matters for SMBs:** Bloom Aesthetics Clinic's customers are making personal aesthetic decisions — often emotionally significant ones. A cold or overly formal AI would erode trust faster than no AI at all. The persona is designed to feel like a helpful person, not a search engine.

---

## 6. Escalation Logic — Full Specification

### Trigger Types

| Type | Detection Method | Example |
|---|---|---|
| `sentiment` | LLM classifier | "I'm absolutely furious about my last visit" |
| `medical_question` | LLM classifier | "Can I have Botox if I'm on blood thinners?" |
| `pricing_negotiation` | LLM classifier | "Can you do it for £150?" |
| `explicit_request` | LLM classifier | "I want to speak to a real person" |
| `safety_concern` | LLM classifier | "My face is swollen from the treatment" |
| `low_confidence` | Threshold check | confidence < 0.6 after 2 misses |
| `out_of_scope` | Gap counter | >2 consecutive unanswered questions |

### Escalation Flow

```
User message received
        │
        ▼
EscalationDetector.check()  ← dedicated LLM classifier call
        │
   escalate=true? ──YES──► Apply escalation, log event, return handoff message
        │
       NO
        │
        ▼
Stage handler (FAQ / Qualification)
        │
   handler flags escalate=true? ──YES──► Apply escalation
        │
       NO
        │
        ▼
EscalationDetector.check_low_confidence() ← confidence threshold check
        │
   confidence < 0.5? ──YES──► Apply escalation
        │
       NO
        │
        ▼
Normal response delivered
```

### Escalation Record (persisted to `logs/events.jsonl`)

```json
{
  "ts": "2025-01-15T14:32:01Z",
  "event_type": "ESCALATION",
  "session_id": "a3f7b2c1",
  "trigger_type": "medical_question",
  "reason": "Customer asked about contraindications with blood thinners.",
  "confidence": 0.95,
  "flagged_message": "Can I have Botox if I'm on warfarin?"
}
```

---

## 7. Stage Transition Logic

```
┌─────────────┐
│     FAQ     │  ← Default starting stage
│             │
│  Answers    │──stage_complete=true ──────────────────────►┌──────────────────┐
│  customer   │                                              │  QUALIFICATION   │
│  questions  │                                              │                  │
│             │                                              │  3 structured    │
│             │──escalation detected ──────────────────────►│  questions,      │
└─────────────┘                        │                    │  one per turn    │
                                        │                    │                  │
                                        ▼                    └──────────────────┘
                               ┌──────────────┐                      │
                               │  ESCALATED   │◄─ escalation ────────┘
                               │              │
                               │  Handoff     │                      │
                               │  message     │              stage_complete=true
                               │  + audit log │                      │
                               └──────────────┘                      ▼
                                                             ┌──────────────────┐
                                                             │     SUMMARY      │
                                                             │                  │
                                                             │  Structured      │
                                                             │  session report  │
                                                             └──────────────────┘
```

**stage_complete semantics:**
- FAQ sets `stage_complete=true` when: the customer's primary question is answered AND the AI has naturally offered to learn more about their needs.
- Qualification sets `stage_complete=true` when: all three questions have been answered (tracked by `qualification_step` counter in state).

---

## 8. Trade-offs & Known Limitations

| Area | Trade-off |
|---|---|
| **Two LLM calls per turn** | The escalation pre-filter adds latency (~0.5–1s). Benefit: defence-in-depth for safety. In production, this could be a fast rule-based pre-filter + LLM for edge cases. |
| **No persistent storage** | `ConversationState` lives in memory. In production, it would be serialised to Redis or a database for multi-channel sessions. |
| **No streaming** | Responses are returned as complete strings. Streaming would improve perceived latency for long responses. |
| **English only** | The SOP and prompts are English-only. Multilingual support would require translated SOPs and language detection. |
| **Confidence is self-reported** | The model assesses its own confidence, which can be over-optimistic. A calibration layer or retrieval-based grounding (RAG) would improve reliability. |

---

## 9. Future Improvements (if extending to production)

1. **RAG over SOP** — embed SOP chunks, retrieve relevant sections per query, reduce prompt length and improve grounding precision.
2. **Streaming responses** — use `stream=True` for perceived latency improvement in WhatsApp delivery.
3. **Human-in-the-loop dashboard** — escalated sessions surface in a coordinator UI with the full transcript and escalation reason pre-filled.
4. **A/B prompt testing** — the prompt abstraction in `system.py` makes it trivial to swap prompt variants and compare escalation rates, CSAT, and qualification completion rates.
5. **Fine-tuned classifier** — replace the LLM-based escalation detector with a small fine-tuned classifier for lower latency and cost.
