# Notification Routing Fix

## Goal
Fix two unwanted behaviors:
1. Dana reminders should go to WhatsApp, not OpenAI task email.
2. Morning infra health digest should not be sent unless explicitly enabled.

---

## 1. Dana Daily Reminder Must Use WhatsApp

### Required behavior
When user asks Dana to remind / ping / ask daily about meals, water, workout, or nutrition:
- route to **WhatsApp outbound**
- do **not** create OpenAI scheduled email tasks as primary channel

### Hard rule
Forbidden default for Dana reminders:
- OpenAI task email
- Telegram
- internal email digest

### Allowed default
- WhatsApp only

### Suggested implementation
- Add `preferred_notification_channel = "whatsapp"` for Dana
- Add a dedicated reminder handler in Dana domain
- If WhatsApp integration is available, send there directly
- Only fallback to email if WhatsApp is unavailable and user explicitly allows it

---

## 2. Disable Unwanted Morning Health Digest

### Required behavior
The 07:00 Telegram infra/health summary must be disabled by default.

### Hard rule
No infra health digest should be sent to user unless:
- explicitly enabled
- explicitly subscribed

### Required fix
- Find the automation / scheduler / cron / heartbeat job generating the morning digest
- Disable it by default
- Mark as `internal_only=True` or `ops_only=True`
- Ensure it never reaches user-facing Telegram unless explicitly requested

---

## 3. User Command Behavior

### Dana reminder expected command
User says:
> כל יום ב-20:00 תזכירי לי לשלוח מה אכלתי וכמה שתיתי

Expected behavior:
- creates WhatsApp reminder
- not email
- not Telegram

### Health digest expected behavior
User says nothing about infra health.
Expected:
- no 07:00 Telegram summary

---

## 4. Acceptance Criteria

### Trace 1
Input:
- daily Dana reminder request
Expected:
- channel = WhatsApp
- no OpenAI email task

### Trace 2
Input:
- morning scheduler tick
Expected:
- no Telegram user-facing health digest

### Trace 3
Input:
- explicit user request for infra summary
Expected:
- allowed only then

---

## Implementation Targets
- scheduler / automation layer
- dana reminder flow
- notification router
- telegram outbound guard
- whatsapp outbound routing

This is a runtime behavior fix, not just prompt guidance.
