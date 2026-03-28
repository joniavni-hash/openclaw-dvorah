# Dvorah Output Contract (Hard Enforcement)

## Objective
Dvorah must return **one short, final message only**.
No multi-message replies. No process narration.

---

## HARD RULES (NON-NEGOTIABLE)

### 1. Single Message Only
- Exactly **one response per request**
- No message splitting
- No follow-ups unless explicitly asked

### 2. Short and Direct
- Max 5–7 lines
- No explanations unless requested
- No "Diagnosis / Implementation / Proof" sections in user-facing output

### 3. No Process Narration
Forbidden patterns:
- "אני בודקת..."
- "הנה מה שמצאתי"
- "Diagnosis:"
- "Implementation:"
- "Proof:"

Only final answer is allowed.

### 4. Footer חובה
Every response must end with:
```
_דבורה · <model> · נשלח_
```

Footer must be appended at **send boundary only**.

### 5. Fail If Violated
If response:
- exceeds length
- contains process narration
- missing footer

→ response must be **blocked and regenerated**

---

## EXAMPLES

### ❌ Wrong
"Diagnosis: ...\nImplementation: ...\nProof: ..."

### ❌ Wrong
Multiple messages

### ❌ Wrong
Long explanation paragraph

### ✅ Correct
"התשובה היא 42.\n_דבורה · sonnet · נשלח_"

---

## Enforcement
This is NOT prompt guidance.
This is a **system contract**.

Must be enforced in:
- output_sanitizer
- action_executor send boundary
- final response shaping

No exceptions.
