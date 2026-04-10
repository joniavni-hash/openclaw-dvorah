# CAPABILITY_INDEX.md
<!-- Status: Canonical -->
<!-- Purpose: System discovery and integration routing -->
<!-- Authority: Source of truth -->

מטרת הקובץ הזה היא גילוי מהיר של מערכות מחוברות ונתיב טעינה נכון.
לפני ששואלים את יוני אם משהו מחובר, בודקים כאן.

## Email
Keywords:
- email
- mail
- inbox
- reply
- send email
- outlook
- gmail
- מייל
- תיבה
- תשובה למייל

Load order:
1. `integrations/OUTLOOK.md`
2. runbook רלוונטי מתוך `runbooks/`
3. `HEARTBEAT.md` רק אם המשימה קשורה לדיג'סט, followup, או בדיקה יזומה

Notes:
- Outlook הוא ברירת המחדל למיילים שוטפים
- Gmail נבדק רק אם יוני ביקש במפורש

## WhatsApp / Groups
Keywords:
- whatsapp
- group
- class group
- message the group
- summarize messages
- ווטסאפ
- קבוצה
- סיכום קבוצה

Load order:
1. `integrations/WHATSAPP.md`
2. `policies/GROUP_BEHAVIOR_POLICY.md`
3. `state/KNOWN_GROUPS.md`
4. `HEARTBEAT.md` אם מדובר בסיכום יומי

## Home / Devices
Keywords:
- control4
- home
- speaker
- tv
- device
- בית חכם
- רמקול
- טלוויזיה

Load order:
1. `integrations/CONTROL4.md`
2. `TOOLS.md` אם צריך שמות מקומיים או כינויים

## Rides / Gett
Keywords:
- gett
- taxi
- cab
- ride
- airport
- order a ride
- מונית
- נסיעה
- הזמיני מונית

Load order:
1. `integrations/GETT.md`
2. `policies/EXTERNAL_ACTIONS_POLICY.md`

Notes:
- אם צריך ממש לבצע הזמנה, דרוש אישור מפורש
- אם לא ברור איזה חשבון להשתמש, שואלים רק על בחירת החשבון, לא על עצם קיום החיבור

## Google Ads
Keywords:
- google ads
- campaign
- keywords
- villa lithos
- קמפיין
- מודעות

Load order:
1. `integrations/GOOGLE_ADS.md`
2. `scripts/google_ads_report.py` for credentials
3. `HEARTBEAT.md` for monitoring schedule

## Google Analytics
Keywords:
- google analytics
- GA4
- website traffic
- villa analytics
- sessions
- users
- conversions
- traffic sources

Load order:
1. `integrations/GOOGLE_ANALYTICS.md`
2. `secrets/.env` for credentials
3. Villa Lithos property analysis

## Gmail / Google Workspace
Keywords:
- gmail
- google calendar
- google sheets
- google docs
- google drive
- contacts
- tasks

Load order:
1. `integrations/GMAIL.md`
2. GOG CLI documentation

Notes:
- Gmail is NOT the default for email
- Outlook is default. Gmail only when explicitly requested.

## GitHub
Keywords:
- github
- git
- repo
- push
- commit

Load order:
1. `integrations/GITHUB.md`

## Vercel
Keywords:
- vercel
- dashboard
- deploy

Load order:
1. `integrations/VERCEL.md`

## Tailscale
Keywords:
- tailscale
- funnel
- tunnel
- vpn

Load order:
1. `integrations/TAILSCALE.md`

## Restaurant Booking / Dining
Keywords:
- restaurant
- booking
- reservation
- table
- ontopo
- tabit
- מסעדה
- הזמנה
- שולחן
- הזמנת מקום
- מסעדות

Load order:
1. `integrations/ONTOPO.md`
2. `integrations/TABIT.md`
3. `state/RESTAURANT_SLUGS.json`

Notes:
- Ontopo is the primary platform for fine dining and chef restaurants
- Tabit is common for casual restaurants and has a mobile app with real-time search
- Many restaurants appear on both platforms
- Restaurant slugs database contains 140+ venues organized by city

## Web Search / Browser
Keywords:
- search
- google
- browse
- website
- חיפוש

Load order:
1. `integrations/CHROME_USER.md`
2. Use profile=user for authenticated/search tasks
3. Fall back to headless openclaw browser for simple fetches

Notes:
- Chrome user browser is the PRIMARY search method
- If Chrome is not running, inform Yoni to start it
