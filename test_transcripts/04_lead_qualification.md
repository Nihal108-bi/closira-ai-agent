# Test Transcript 4 — Lead Qualification

**Scenario:** Customer engages via FAQ stage, then the AI transitions to the lead qualification stage and collects structured answers to all 3 questions. The session ends with a populated LeadData object.

**Expected behaviour:** Smooth FAQ → Qualification transition. Three questions asked one at a time. Answers extracted and stored. Warm, non-interrogative tone throughout.

---

**Session ID:** `demo-04`  
**Stage:** FAQ → QUALIFICATION → SUMMARY

---

```
Bloom 🌸: Hello! Welcome to Bloom Aesthetics Clinic. I'm Bloom, your AI assistant.
           How can I help you today?

Customer:  Hi, I'm interested in lip fillers.

           [Stage: FAQ]

Bloom 🌸: How lovely! Lip fillers are one of our most popular treatments. Our Dermal
           Fillers start from £250 and the treatment itself takes around 30–45 minutes.

           You'll see results straight away, though full results are visible after any
           mild swelling settles (usually within 5–7 days). Results typically last 6–12
           months for lips.

           As a new patient, your first step would be a free 30-minute consultation
           with our aesthetic practitioner — no commitment needed, just a chance to
           chat through exactly what you're looking for.

           Would you like to find out more, or shall I ask a couple of quick questions
           so our team can make the most of your consultation? 😊

Customer:  Yes, please — I'd love to tell you more.

           [Stage transition: FAQ → QUALIFICATION]

Bloom 🌸: Wonderful! Just three quick ones. First:

           What treatment are you most interested in — Botox, Fillers, or would you
           like to start with a free Consultation?

Customer:  Lip fillers please.

           [Extracted: treatment_interest = "Lip fillers"]

Bloom 🌸: Perfect, noted! Lip fillers it is. 💛

           Next question: Have you had any aesthetic treatments before, or would this
           be your first time?

Customer:  No, it would be my first time.

           [Extracted: prior_experience = "No prior aesthetic treatments — first time"]

Bloom 🌸: That's absolutely fine — our practitioners are brilliant with first-timers
           and will make sure you feel completely comfortable.

           Last one: Is there a specific concern or area you'd like to address, or are
           you still exploring your options?

Customer:  I want to add a bit of volume and definition to my lips. They've always
           been quite thin and I'd like a natural look.

           [Extracted: goals_or_concerns = "Add volume and definition to thin lips, natural look preferred"]

Bloom 🌸: That's really helpful, thank you! A natural, defined look is exactly what
           our practitioners specialise in — you're in great hands.

           That's everything I needed! Here's a quick summary of your session:

           [SUMMARY generated — see Scenario 5 for full format]
```

---

**Lead Data Collected:**

```json
{
  "treatment_interest": "Lip fillers",
  "prior_experience": "No prior aesthetic treatments — first time",
  "goals_or_concerns": "Add volume and definition to thin lips, natural look preferred",
  "contact_name": null,
  "additional_info": {}
}
```

---

**Evaluation Notes:**

| Check | Result |
|---|---|
| FAQ → Qualification transition natural and unprompted | ✅ |
| Questions asked one at a time (not all at once) | ✅ |
| Previous answer acknowledged before asking next question | ✅ |
| All 3 answers extracted and stored correctly | ✅ |
| Tone remains warm, not interrogative | ✅ |
| `qualification_step` counter incremented correctly (0 → 1 → 2) | ✅ |
| `stage_complete=true` after 3rd answer | ✅ |
| Smooth transition to Summary stage | ✅ |
