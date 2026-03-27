# Dana v2 Master Spec — Performance OS

## Vision
Dana should evolve from a fitness responder into a full **Body / Performance Operating System**.

Dana v2 adds four missing layers:
1. Health data ingestion (iPhone / Apple Health / Apple Watch bridge)
2. Daily close accountability loop
3. Weekly coaching loop
4. Readiness / fatigue-aware decisioning

---

## Goals
Dana should be able to:
- understand what the user did physically today
- understand what the user ate today
- estimate adherence and momentum
- decide whether to push, maintain, or recover
- close the day with a short coaching summary
- run a weekly review automatically

---

## v2 Architecture

### 1. Health Data Bridge
Dana should support an ingestion layer for health and activity data.

#### Supported sources (v2 target)
- Apple Health / HealthKit
- Apple Watch workouts
- Apple Shortcuts export
- Manual fallback logs

#### Initial ingestion contract
Dana should be able to accept a daily JSON or markdown payload containing:
- date
- steps
- active_calories
- workouts_count
- workout_minutes
- distance_km
- standing_hours
- sleep_hours (optional)
- resting_hr (optional)
- hrv (optional)
- weight (optional)

#### Proposed local file
`state/fitness_health_log.json`

#### Proposed write / read behavior
- append one daily record per date
- if same date exists, update not duplicate
- Dana can read latest 14 days for readiness / review logic

---

### 2. Daily Close Mode
Dana should support a dedicated **daily_close** task.

#### Trigger examples
- "סיכום יום"
- "בואי נסגור את היום"
- nightly reminder flow

#### Output contract
Dana daily_close must return:
- protein_total
- calories_total
- workout_done
- steps_done
- day_score
- what_went_well
- what_hurt_progress
- tomorrow_focus
- single_best_move

#### Desired response style
Short, sharp, coach-like.
No fluff.
No motivational spam.

---

### 3. Weekly Coaching Review
Dana should support a stronger **weekly_review_v2** mode.

#### It should compute:
- weekly_weight_trend
- protein_consistency_score
- workout_consistency_score
- steps_consistency_score
- adherence_score
- biggest_leak
- strongest_habit
- one_change_for_next_week

#### Optional later additions
- streak count
- weekend drift detection
- high-risk days detection

---

### 4. Readiness / Fatigue Layer
Dana should support a **readiness_decision** mode.

#### Inputs can include:
- sleep_hours
- workouts last 3 days
- steps / movement
- subjective fatigue from message
- soreness / low motivation phrases

#### Dana should classify the day into:
- push_day
- maintain_day
- recovery_day

#### Output contract
- readiness_state
- should_train_today
- recommended_intensity
- recommended_duration
- fallback_option
- nutrition_priority_today

---

### 5. Daily Reminder Compatibility
Dana should work well with the nightly reminder already created.

#### Reminder expectation
At night, user sends:
- what they ate
- snacks
- drinks
- workout if any

Dana should then be able to:
- log it
- estimate it
- summarize the day
- tell user exactly what happened

---

### 6. New Task Types to add
Dana classifier should support:
- `daily_close`
- `readiness_decision`
- `health_sync`
- `weekly_review_v2`

---

### 7. New Suggested State Helpers
Suggested helper functions:
- `_load_health_log()`
- `_merge_health_day_record()`
- `_compute_readiness()`
- `_compute_daily_close()`
- `_compute_adherence_score()`
- `_detect_weekend_drift()`

---

### 8. UX / Tone Rules
Dana should sound like:
- practical
- direct
- useful
- slightly coach-like
- not soft
- not overexplaining

Avoid:
- generic wellness talk
- influencer tone
- empty encouragement

---

## Suggested v2 Rollout Order
1. Add health data file support
2. Add daily_close mode
3. Add readiness decision mode
4. Upgrade weekly review
5. Add automation / routine support

---

## Proof required after implementation
At least 8 traces:

1. Health sync payload ingested
2. "סיכום יום" → daily_close
3. "ישנתי 5 שעות, שווה להתאמן?" → readiness_decision
4. "היום עשיתי 11,000 צעדים" → health sync / daily state
5. "מה מצב השבוע שלי?" → weekly_review_v2
6. "אני גמור ואין לי כוח" → recovery-aware decision
7. Nightly reminder response → day close works
8. Weekly review shows adherence + biggest leak

---

## Goal of Dana v2
Not a chatbot.
Not a food logger.
Not a workout generator.

Dana v2 should become:
# a lightweight personal performance operating system
