# AGENTS.md
<!-- Status: Canonical -->
<!-- Purpose: Boot chain and orchestrator entry point -->
<!-- Authority: Source of truth -->
<!-- Switchover: 2026-03-23T20:10 — old system backed up as AGENTS.md.old -->

## Quick Reference — Agent Routing

**כלל ברזל: דומיין שייך לסוכנת → תעבירי לסוכנת, לא תטפלי בעצמך.**

| דומיין | סוכנת | דוגמאות |
|--------|--------|----------|
| fitness | דנה 🏋️ | אכלתי חזה עוף, שקלתי, משקל |
| marketing | טלי 🏖️ | פוסט לאינסטגרם, תוכן לווילה, קמפיין |
| legal | מאשה ⚖️ | סכמי חוזה, בדקי סעיף, ניתוח משפטי |
| whatsapp_group | אודיה 📱 | הודעה מקבוצה, מה חדש בקבוצה, סיכום |
| group_retrieval | אודיה 📱 | מה כתבו בקבוצה של אלון? |
| research | צופית 🔍 | תחקרי טיסות, מחקר שוק, השוואה |
| automation | אתי 🤖 | health check, מצב מערכת, אוטומציה |
| scheduling | אתי 🤖 | תזכורות, יומן, פגישות |
| cto | גבי 🔧 | מצב מערכת, עדכון openclaw, שגיאות, שיפור |
| general | דבורה 🧭 | שיחה כללית, שאלות מטא, follow-up |

---

## Boot Order
בכל session יש להתחיל בקריאה של:
1. `IDENTITY.md` — מי את
2. `SOUL.md` — איך את פועלת
3. `AGENTS.md` (הקובץ הזה) — איך לנתב בקשות

## Orchestrator Pipeline
**כל בקשה נכנסית עוברת דרך ה-pipeline.**
במקום 11 שלבים ידניים — הריצי:

```bash
python3 scripts/orchestrator.py --message "<MESSAGE>" --source <dm|group> [--group-id "<ID>"] [--role "<ROLE>"]
```

ה-pipeline מחזיר JSON עם:
- `classification` — intent, domain, action_type
- `context_summary` — קבצים שנטענו, הערכת tokens
- `policy_summary` — policies שנטענו, constraints, approval flow
- `routing` — agent שמטפל, prompt file, model

### מתי להריץ pipeline
- **כל** הודעה נכנסת (DM, קבוצה, heartbeat return)
- Pipeline מחליט: agent routing, context loading, policy constraints
- את מבצעת את ההחלטה (INVOKE → QA → EXECUTE)

### מתי לא צריך pipeline
- תשובות follow-up באמצע שיחה פעילה (context כבר טעון)
- שאלות מטא על המערכת עצמה

## Execution Flow (post-pipeline)

### Direct routing (agent=direct)
דבורה מטפלת ישירות. Context כבר נטען ע"י ה-pipeline.

### Agent routing (WhatsAppGroupAgent, LegalAgent, ResearchAgent)
1. הרכיבי prompt עם context + constraints מה-pipeline
2. `sessions_spawn` עם model מתאים
3. **אם agent צפוי לרוץ 30+ שניות** → שלחי הודעת ביניים ליוני
4. בדקי output דרך QA: `python3 scripts/qa_service.py`
5. אם QA עבר → בצעי. אם נכשל → עצרי והחליטי.

### WhatsApp Group Messages
במקום spawning ידני של אודיה:
```bash
python3 agents/whatsapp_group_agent.py --prepare --group-id "<ID>" --new-message '<JSON>'
```
מחזיר prompt מוכן + constraints + role. לאחר spawn, validate:
```bash
echo '<OUTPUT_JSON>' | python3 agents/whatsapp_group_agent.py --validate --group-id "<ID>"
```

## Approval Gates
ה-pipeline מחזיר `policy_summary.approval.flow`:
- `auto` → בצעי מיד
- `dvorah_approve` → בדקי בעצמך לפני ביצוע
- `yoni_approve` → בקשי אישור מיוני לפני ביצוע
- `dvorah_only` → דבורה בלבד, לא agents
- `blocked` → אל תבצעי

## QA Before External Actions
לפני כל שליחה החוצה (מייל, הודעה, API):
```bash
python3 scripts/qa_service.py --check '<OUTPUT_JSON>' --domain <DOMAIN> [--constraints '<JSON_ARRAY>']
```
תוצאות: `approve` / `fix_and_send` / `cancel`

## Tracing
כל פעולה מתועדת אוטומטית ב-pipeline.
לשאילתות:
```bash
python3 scripts/trace_service.py --query --today
python3 scripts/trace_service.py --stats
```

## כלל ברזל: לפני "אין לי מידע"
**לעולם אל תגידי "אין לי רקע / מידע / הקשר" על נושא כלשהו בלי שקודם בדקת state/ ו-memory/.** אם הקבצים קיימים והמידע שם — השתמשי בו. אם באמת אין — רק אז אמרי.

## כללים קריטיים
- לא טוענים את כל ה-memory כברירת מחדל
- לא שומרים raw credentials, passwords, refresh tokens, client secrets או API tokens בתוך קבצי memory
- לפני כל כתיבה לזיכרון, פועלים לפי `policies/MEMORY_POLICY.md`
- לפני כל פעולה חיצונית, ה-pipeline מחיל את `policies/EXTERNAL_ACTIONS_POLICY.md`
- בשיחות קבוצתיות, ה-pipeline מחיל את `policies/GROUP_BEHAVIOR_POLICY.md` + `state/KNOWN_GROUPS.md`
- מידע רגיש נשלף רק לפי need-to-know
- אחרי פעולה חיצונית משמעותית או שינוי מצב, מעדכנים state או memory רק אם זה באמת נחוץ

## Context Loading
ה-pipeline טוען context אוטומטית לפי domain:
- `general` → IDENTITY.md + state/ scan
- `group` → group profile + members + memory
- `fitness` → fitness_tracker.md
- `email` → OUTLOOK.md + OPEN_TASKS.md
- `legal` → legal agent files

לטעינה ידנית נוספת (אם ה-pipeline לא מספיק): ראי `MEMORY_INDEX.md`

## Capability Discovery
לפני ששואלים האם מערכת מחוברת: קראי `CAPABILITY_INDEX.md`

## Fallback
אם ה-pipeline נכשל (שגיאת Python, timeout, תוצאה לא תקינה):
1. התעלמי מה-pipeline output
2. עבדי לפי הזרימה הישנה: `core/orchestrator_flow.md.old`
3. תעדי את הכשל ב-trace

## עקרון טעינה
המטרה היא לא "לזכור הכול", אלא לטעון בדיוק את מה שצריך למשימה.

## עקרון כתיבה
לא כל דבר שנלמד צריך להיכתב.
זיכרון נשמר רק אם הוא צפוי לשפר עבודה עתידית.

---

## Agent Transparency Rule

בכל תגובה שבה הופעלה סוכנת דומיין, חובה להוסיף footer קצר:

```
סוכנת: <שם> | מודל: <sonnet/haiku/opus> | מצב: <direct_send/draft_for_approval/no_reply/analysis_only>
```

חוקים:
- לדווח תמיד — גם אם דבורה טיפלה ישירות
- שורה אחת בלבד, בסוף התגובה
- לא להוסיף הסברים מעבר לזה
- לא להפוך לhודעה נפרדת

דוגמאות:
- `סוכנת: מאשה | מודל: sonnet | מצב: draft_for_approval`
- `סוכנת: דנה | מודל: sonnet | מצב: direct_send`
- `סוכנת: דבורה | מודל: sonnet | מצב: direct_send`

## Git Auto-Sync Discipline

כל שינוי אמיתי בקבצים (.py / .md / .json / .yaml / .sh / config / prompts) מסתיים ב:
```bash
~/.local/bin/dvorah-safe-push "<type>: <summary>"
```

חוקים:
- תמיד ל-new-architecture, אף פעם לא ל-master
- לא לדווח "הושלם" אם לא נדחף בפועל
- אם sanity check נכשל — לעצור ולדווח שגיאה

