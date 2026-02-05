# AI Specialist Proposal: AI/LLM Integration Design for ankicli-v2

## 1. TOOL NOTES SYSTEM

### Design: Append notes to tool descriptions at runtime

```python
def _get_tools_with_notes(self) -> list[dict]:
    tools = []
    for tool in ANKI_TOOLS:
        tool_copy = {**tool}
        note = self.config.tool_notes.get(tool["name"])
        if note:
            tool_copy["description"] += f"\n\nUSER PREFERENCE: {note}"
        tools.append(tool_copy)
    return tools
```

3 new tools: set_tool_note, get_tool_notes, remove_tool_note.

Claude proactively detects preferences and offers to save them.

---

## 2. TRANSLATION PRACTICE EVALUATION

### Architecture: Claude evaluates in conversation, no separate eval tool needed.

**Evaluation Rubric (in system prompt):**
1. MEANING: Does the translation convey the same meaning? Accept semantic equivalence.
2. GRAMMAR: Verb conjugation, gender agreement, preposition usage.
3. NATURALNESS: Would a native speaker say this?
4. VOCABULARY: Did they use appropriate vocabulary?

**Adaptive Difficulty:**
- 3+ correct in a row: increase complexity
- 2+ wrong in a row: simplify and review grammar
- Track error patterns across sessions

---

## 3. GRAMMAR QUIZ GENERATION

### Claude generates questions dynamically based on:
- User's CEFR level from learning summary
- Grammar gaps in what_to_learn
- Known vocabulary (so grammar is the focus)

### Session flow in system prompt:
1. Warm-up questions on known grammar
2. Introduce target concept with explanation
3. Practice questions with increasing difficulty
4. Mixed review
5. Summary with what to study next

---

## 4. SYSTEM PROMPT OPTIMIZATION

### Modular Architecture:

```python
def build_system_prompt(config, learning_summary):
    sections = [
        CORE_IDENTITY,           # ~500 tokens
        CARD_FORMAT_GUIDE,       # ~800 tokens
        GENERAL_GUIDELINES,      # ~400 tokens
        LEARNING_SUMMARY_GUIDE,  # ~400 tokens
        CONTEXT_MANAGEMENT,      # ~100 tokens
    ]
    if config.tool_notes:
        sections.append(TOOL_NOTES_GUIDE)
    sections.append(TRANSLATION_GUIDE)
    sections.append(GRAMMAR_QUIZ_GUIDE)
    sections.append(format_level_context(current_level))
    return "\n\n".join(sections)
```

### Level-Aware Context Injection:
```
## Your Current Student
- Active level: A2 (95%) / B1 (25%)
- Strong areas: preterite, imperfect, reflexive verbs
- Weak areas: conditional tense, indirect object pronouns
- 276 cards total, last session: 2026-02-04
```

---

## 5. ADDITIONAL AI FEATURES

### 5A. Smart Review Suggestions
Analyze deck stats + learning summary + practice history -> prioritized study plan.

### 5B. Contextual Sentence Generator
For any word, generate examples in different contexts (conversation, formal, narrative, email).

### 5C. Error Pattern Analysis
Analyze practice sessions to identify systematic errors and generate targeted micro-lessons.

### 5D. Vocabulary Network Builder
Map word relationships, suggest related words when adding cards.

### 5E. Pronunciation Guide
Phonetic guidance for tricky words (ll, rr, ñ, stress patterns).

---

## 6. TOKEN/COST ANALYSIS

After all changes: ~3,900 additional tokens per turn (~4-10% increase).
Main cost driver remains conversation length, handled by existing compaction.

---

## PRIORITY:
1. Tool Notes (LOW complexity, HIGH impact)
2. Translation Practice (MEDIUM, HIGH)
3. Grammar Quizzes (MEDIUM, HIGH)
4. System Prompt Modularization (MEDIUM, MEDIUM)
5. Smart Review Suggestions (LOW, MEDIUM)
6. Error Pattern Analysis (MEDIUM, MEDIUM)
7. Vocabulary Network Builder (LOW, MEDIUM)
