# Anthropic Cost Reporter Spec

## Goal
Enable Dvorah to answer exactly:
- how many tokens were spent today
- how much they cost today

Using authoritative sources only:
1. Anthropic Console usage/billing pages
2. Anthropic Admin / Usage API if available
3. fallback: internal provider logs if Anthropic data unavailable

---

## Required User Command
User can write:

> כמה בזבזת היום

Dvorah must answer ONLY with:
- total input tokens today
- total output tokens today
- total cache read / write tokens if available
- estimated or exact USD cost today
- source used
- timestamp of calculation

No fluff.

---

## Required Implementation

### 1. Add provider usage collector
Create a collector that can pull today's usage from Anthropic source of truth.

Suggested file:
- `integrations/anthropic_usage.py`

Required function:
```python
def get_today_anthropic_usage() -> dict:
    """
    Returns:
    {
      "date": "YYYY-MM-DD",
      "input_tokens": int,
      "output_tokens": int,
      "cache_creation_tokens": int | None,
      "cache_read_tokens": int | None,
      "usd_cost": float,
      "source": str,
      "calculated_at": str,
    }
    """
```

### 2. Preferred data sources
Use in this order:
1. Anthropic official usage / admin / billing API
2. Anthropic Console-exported usage endpoint if authenticated
3. internal logs only as fallback

### 3. Normalize pricing
Map usage to exact model pricing for the models actually used today.

At minimum support:
- Claude Sonnet
- Claude Opus
- Claude Haiku

Cost must be computed from official Anthropic pricing if API does not return cost directly.

### 4. Add agent command route
When user asks any of:
- "כמה בזבזת היום"
- "כמה עלו הטוקנים היום"
- "כמה עלה אנתרופיק היום"
- "today token cost"

Dvorah should call the collector and answer directly.

### 5. Strict response format
Required response format:

```text
היום עד עכשיו:
- input tokens: X
- output tokens: Y
- cache write: Z
- cache read: W
- עלות: $N.NN
- מקור: SOURCE
- חושב ב: TIMESTAMP
```

If exact source unavailable:

```text
היום עד עכשיו (הערכה):
- input tokens: X
- output tokens: Y
- עלות: $N.NN
- מקור: internal logs + Anthropic pricing
- חושב ב: TIMESTAMP
```

### 6. Hard rules
Forbidden:
- guessing without marking estimate
- vague wording like "probably" or "roughly" unless fallback path used
- answering without source

Required:
- exact if possible
- estimate only if exact unavailable
- include source every time

---

## Acceptance Test
User:
> כמה בזבזת היום

Expected:
A compact exact token+cost answer from Anthropic source of truth.
