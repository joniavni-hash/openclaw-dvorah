# Notification Routing Fix

## Goal
Fix two unwanted behaviors:
1. Dana reminders should go to WhatsApp, not OpenAI task email.
2. Morning infra health digest should not be sent unless explicitly enabled.

## Required behavior
- Dana meal/water reminders default to WhatsApp only
- Never create OpenAI scheduled email tasks for Dana reminders by default
- Disable 07:00 Telegram health digest by default
- Internal ops / infra summaries must be ops_only unless explicitly enabled by user

## Acceptance
1. Dana reminder request -> WhatsApp only
2. Morning scheduler tick -> no Telegram digest
3. Explicit infra summary request -> allowed
