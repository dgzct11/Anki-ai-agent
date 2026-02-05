# UI/UX Design Proposals for ankicli-v2

## Current UI Inventory

The app uses Rich library components: Console, Panel, Markdown, Text, Progress, Table, console.status(), prompt_toolkit.

Color scheme: cyan (headings), green (success), yellow (warnings), red (errors), dim (metadata), blue (panels), orange1 (context warnings).

---

## FEATURE 1: Translation Practice Mode

### Interaction Flow

**Session Start Panel:**
```
+-----------------------------------------------------------+
|  TRANSLATION PRACTICE                                     |
|  Deck: Spanish A2         Level: A2                       |
|  Words: 10 (5 new, 5 review)  Focus: mixed               |
|  Commands: /skip  /hint  /quit  /score                    |
+-----------------------------------------------------------+
```

**Each Question:**
```
  Question 3/10                              [review word]
+-----------------------------------------------------------+
|  Translate to Spanish:                                    |
|  "I need to find a doctor because my head hurts."         |
|  Target words: encontrar, doler                           |
+-----------------------------------------------------------+
Tu traducción: ...
```

**Feedback (correct/partial/incorrect):**
- Green panel for correct with notes
- Yellow panel for partial with corrections highlighted
- Red panel for incorrect with model answer and key lessons

**Session Summary:**
```
+===========================================================+
|  PRACTICE SESSION COMPLETE                                |
|  Score: 7/10 (70%)  [===████████░░░] 70%                 |
|  Correct: 5  |  Partial: 2  |  Incorrect: 3              |
|  Weak areas: indirect object pronouns, por vs para        |
+===========================================================+
```

---

## FEATURE 2: Grammar Quizzes

### Question Types with Rich UI:

**Fill in the Blank:** Panel with blank, verb in parentheses
**Multiple Choice:** Numbered options in cyan
**Conjugation Challenge:** Table format for all persons
**Sentence Transformation:** Present -> target tense
**Quiz Summary:** Score bar, by-type breakdown, recommendations

---

## FEATURE 3: Tool Notes Configuration

```
+-----------------------------------------------------------+
|  TOOL NOTES & PREFERENCES                                 |
|  1. [cyan]add_card[/cyan]                                 |
|     "Always use 5 examples. Use informal Spanish."        |
|  2. [cyan]General[/cyan]                                  |
|     "Latin American Spanish, not Castilian."              |
|  Commands: notes add | notes edit | notes remove          |
+-----------------------------------------------------------+
```

---

## FEATURE 4: Progress Dashboard

Rich dashboard with:
- Header Panel (DOUBLE box, cyan border)
- Overall progress bar
- Per-level sections with WHAT I KNOW / WHAT TO LEARN columns
- CEFR concrete numbers: "142/500 A1 words (28%)"
- Category breakdowns per level
- 14-day activity heatmap
- Grammar mastery checklist

---

## FEATURE 5: CEFR Deep-Dive View

`progress A2` shows every category with known/missing words, grammar checklist with mastered/unmastered, and actionable recommendations.

---

## FEATURE 6: Welcome Dashboard

```
+===========================================================+
|  Anki Assistant v0.1.0                                    |
|  Model: Claude Opus 4.6  |  Deck: Spanish A2 (276 cards) |
|  A1: 80/320  A2: 147/500  B1: 12/650                     |
|  Today's suggestion: "Complete A1 Days/Months (4 left)"   |
|  Commands: chat  practice  quiz  progress  cefr  exit     |
+===========================================================+
```

---

## FEATURE 7: Session Timer & Stats Bar

```
Context: [████░░░░░░] 23% | 12 min | +5 cards | A2: 147/500
```

---

## Design Principles

1. Consistency: Reuse existing Panel/color patterns
2. Progressive disclosure: Overview first, details on interaction
3. Terminal-first: Respect 70-char width, no horizontal scroll
4. Keyboard-driven: Numbers for choices, Enter to continue, /commands
5. Rich library feasibility: Every element maps to real components
6. Minimal disruption: New features are additive
