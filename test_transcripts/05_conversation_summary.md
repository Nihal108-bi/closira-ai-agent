# Test Transcript 5 — Full Session with Conversation Summary

**Scenario:** End-to-end session. Customer asks multiple FAQ questions (one of which reveals a SOP gap), transitions to qualification, and the session ends with a complete structured summary.

**Expected behaviour:** Multi-turn FAQ handling, SOP gap detection and logging, smooth qualification flow, and a structured ConversationSummary with all required fields populated.

---

**Session ID:** `demo-05`  
**Stage:** FAQ → FAQ → FAQ (gap detected) → QUALIFICATION → SUMMARY

---

```
Bloom 🌸: Hello! Welcome to Bloom Aesthetics Clinic. I'm Bloom, your AI assistant.
           How can I help you today?

Customer:  Hello! What services do you offer?

           [Stage: FAQ | confidence: 0.99 | sop_gap: false]

Bloom 🌸: Hi there! We offer the following treatments at Bloom Aesthetics Clinic:

           • Botox (Anti-Wrinkle Injections) — from £200
             Targets forehead lines, crow's feet, frown lines, and more.

           • Dermal Fillers — from £250
             Great for lips, cheeks, jawline, nasolabial folds, and more.

           • Free Initial Consultation (30 minutes)
             A no-commitment chat with our aesthetic practitioner — recommended
             for all new patients before any treatment.

           Is there a particular treatment you'd like to know more about? 😊

Customer:  How much are fillers?

           [Stage: FAQ | confidence: 0.99 | sop_gap: false]

Bloom 🌸: Our Dermal Fillers start from £250. The final price depends on the specific
           area being treated and the amount of product used, which your practitioner
           will confirm during your free consultation.

           Results are immediate, lasting 6–18 months depending on the area — lips
           typically last 6–12 months, while cheeks and jawline can last up to 18 months.

           Would you like to know more, or shall we look at getting you booked in?

Customer:  Do you do evening appointments?

           [Stage: FAQ | confidence: 0.15 | sop_gap: true]
           [SOP gap logged: "Customer asked about evening appointments — not covered in SOP"]

Bloom 🌸: That's a great question! I don't have specific information about evening
           appointment availability in the details I have to hand.

           I'd recommend checking directly via WhatsApp or the website, where the team
           can confirm the latest availability for you.

           Is there anything else I can help you with?

Customer:  Sure, I'd love to tell you more about what I'm after.

           [Stage transition: FAQ → QUALIFICATION]

Bloom 🌸: Brilliant! Let me ask you a few quick questions so our team has everything
           they need for your visit.

           First: What treatment are you most interested in — Botox, Fillers, or would
           you like to start with a free Consultation?

Customer:  Cheek fillers.

           [Extracted: treatment_interest = "Cheek fillers"]

Bloom 🌸: Cheek fillers — excellent choice! Perfect for restoring and contouring volume.

           Next: Have you had any aesthetic treatments before, or would this be your
           first time?

Customer:  Yes, I've had Botox before but never fillers.

           [Extracted: prior_experience = "Has had Botox before, but fillers would be a first"]

Bloom 🌸: That's really helpful to know — you already have a sense of what the
           experience is like, which is great.

           Last question: Is there a specific concern or area you'd like to address,
           or are you still exploring your options?

Customer:  I want to restore some volume — I've lost a lot in my cheeks over the
           years and I'd love a more lifted, youthful look.

           [Extracted: goals_or_concerns = "Restore lost cheek volume, achieve a lifted and youthful appearance"]

           [stage_complete = true → SUMMARY generated]

Bloom 🌸: That's really helpful, thank you so much! Volume restoration in the cheeks
           is something our practitioners absolutely excel at.

           That's everything I needed! Here's a quick summary of your session:
```

---

**Generated Conversation Summary:**

```
────────────────────────────────────────────────────────────
  SESSION SUMMARY  •  ID: demo-05
────────────────────────────────────────────────────────────
  Customer Intent    : Customer enquiring about cheek filler treatment
                       for volume restoration and a more youthful appearance.
  Stage Reached      : SUMMARY
  Session Duration   : 187s
  Total Turns        : 7

  Lead Data Collected:
    Treatment Interest : Cheek fillers
    Prior Experience   : Has had Botox before, but fillers would be a first
    Goals / Concerns   : Restore lost cheek volume, achieve a lifted and
                         youthful appearance

  SOP Gaps Identified:
    • Customer asked about evening appointment availability — not in SOP

  Escalation Occurred : None

  Recommended Next Action:
    Book a free consultation for cheek filler assessment. Flag that customer
    is Botox-experienced but new to fillers — practitioner should set realistic
    volume expectations. Follow up on evening availability question with
    front-desk team.
────────────────────────────────────────────────────────────
```

---

**Structured Summary JSON (internal):**

```json
{
  "session_id": "demo-05",
  "customer_intent": "Customer enquiring about cheek filler treatment for volume restoration and a more youthful appearance.",
  "stage_reached": "summary",
  "lead_data": {
    "treatment_interest": "Cheek fillers",
    "prior_experience": "Has had Botox before, but fillers would be a first",
    "goals_or_concerns": "Restore lost cheek volume, achieve a lifted and youthful appearance"
  },
  "sop_gaps": [
    "Customer asked about evening appointment availability — not covered in SOP"
  ],
  "escalation_event": null,
  "recommended_next_action": "Book a free consultation for cheek filler assessment. Flag that customer is Botox-experienced but new to fillers — practitioner should set realistic volume expectations. Follow up on evening availability question with front-desk team.",
  "total_turns": 7,
  "duration_seconds": 187.0
}
```

---

**Evaluation Notes:**

| Check | Result |
|---|---|
| Multi-turn FAQ handled correctly | ✅ |
| SOP gap (evening appointments) detected and logged | ✅ |
| AI did not invent evening appointment info | ✅ |
| Smooth, natural FAQ → Qualification transition | ✅ |
| All 3 qualification answers extracted correctly | ✅ |
| Summary includes: customer_intent, lead_data, sop_gaps, next_action | ✅ |
| SOP gap appears in summary `sop_gaps` list | ✅ |
| `recommended_next_action` is specific and actionable | ✅ |
| No escalation despite SOP gap (gap count was 1, threshold is 2) | ✅ |
| Session duration and turn count accurate | ✅ |
