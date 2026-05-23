# Test Transcript 1 — In-SOP Question

**Scenario:** Customer asks about Botox prices. The AI must answer accurately from the SOP only — no hallucination, no approximation.

**Expected behaviour:** Accurate price from SOP (`£200 from`), duration info, offer to help further.

---

**Session ID:** `demo-01`  
**Stage:** FAQ → FAQ

---

```
Bloom 🌸: Hello! Welcome to Bloom Aesthetics Clinic. I'm Bloom, your AI assistant.
           How can I help you today?

Customer:  Hi! What are your Botox prices?

Bloom 🌸: Great question! Our Botox (anti-wrinkle injections) start from £200.
           The exact price depends on the number of areas treated, which your
           practitioner will confirm during your free consultation.

           Would you like to know anything else about Botox, or shall I tell you
           about what the treatment involves?

Customer:  How long does it last?

Bloom 🌸: Botox results typically last 3–4 months on average, though this can vary
           depending on the individual and the area treated.

           You'll start to see the initial effects within 3–7 days, with full results
           visible at the 2-week mark.

           Is there anything else you'd like to know, or would you like to take the
           next step and book a free consultation? 😊

Customer:  Great, can I book a consultation?

Bloom 🌸: Absolutely! You can book your free 30-minute consultation via WhatsApp or
           through our website — whichever is easiest for you.

           As a new patient, you'll also need to complete a brief health questionnaire
           before your first appointment. Other than that, you're all set!

           Before I let you go, would it be okay if I asked you a couple of quick
           questions to help our team prepare for your visit?
```

---

**Evaluation Notes:**

| Check | Result |
|---|---|
| Price matches SOP exactly (£200 from) | ✅ |
| Duration matches SOP (3–4 months) | ✅ |
| No invented details (no specific clinic address, practitioner names, etc.) | ✅ |
| Booking channels correct (WhatsApp + website) | ✅ |
| Consultation correctly stated as free | ✅ |
| Natural transition to qualification offered | ✅ |
| `sop_gap_detected` | `false` |
| `confidence` | `0.98` |
| `escalate` | `false` |
