# HEARTBEAT.md
<!-- Status: Canonical -->

## כללים
- כל משימה מופעלת פעם ביום בלבד (אלא אם צוין אחרת)
- לא לפעול בין 22:00-07:00
- אם אין כלום → HEARTBEAT_OK

---

## לוח זמנים

| שעה | משימה |
|-----|--------|
| 07:00-09:00 | `python3 scripts/health_check.py` — כשלון בלבד → דווחי |
| 08:00-10:00 | `python3 core/research_scheduler.py run-scheduled` — 3+ משימות → תמצית |
| 09:00-11:00 | Villa: תעדי ב-villa-lithos/analytics/weekly_operating_log.md |
| 12:00-14:00 | בדקי OPEN_TASKS.md — 🔴 3+ ימים / 🟡 7+ ימים / deadline עבר → תזכורת |
| 18:00-20:00 | `python3 scripts/group_messages.py "120363418497534459" --days 1` → אודיה מסכמת → שלחי ל-120363425514726135@g.us |
| 20:00-22:00 | סיכום יומי (מיילים/בוצע/משימות/למחר, מקס 15 שורות) |
| 21:00+ | כתבי memory/YYYY-MM-DD.md |
| 21:00+ | X/Twitter: אם 3+ ימים מ-24.3.2026 → `python3 scripts/x_feed.py` → סיכום |

## ראשון בלבד
- 07:30-09:00: "בוקר טוב! יום שקילה — תעלה על המשקל ותשלח לי."
- 09:00-11:00: `python3 core/research_scheduler.py message-briefing 168` → briefing
- 09:00+: `python3 scripts/metrics.py` → סיכום
- 19:30+: סיכום דיאטה שבועי

## מוצ"ש בלבד
- 20:00+: סיכום כושר שבועי (משקל/קק"ל/חלבון/מגמה)

## תקופתי
- כל 35 ימים מ-23.3.2026 (מועד הבא: 27.4.2026): תזכורת אוכל כלבים — Hills W/D 10ק"ג, All4Pet, joni.avni@gmail.com_2/nivi2026
- שבועי: סרקי memory/corrections.md — קטגוריה 3+ → כלל חדש ב-SOUL
- שבועי: 5+ קבצי memory/2026-*.md → הרצי runbooks/WEEKLY_SUMMARIZE.md

## לופים פתוחים (12:00)
- פעולה חיצונית לא אומתה → בדקי
- שאלה 24-48ש' בלי תשובה → תזכורת אחת
- שאלה 48+ → stale
- לופ 7+ ימים → סגירה שקטה
- מקס 3 לופים לhearbeat
