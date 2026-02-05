# Language Learning Specialist -- Pedagogical Design Proposal

## 1. TRANSLATION PRACTICE DESIGN

### Core Pedagogical Principle: Active Recall + Productive Skills
Translation practice is the single most impactful feature we can add. Recognizing a word on a flashcard (receptive) is much easier than producing it in context (productive). Translation practice bridges this gap.

### How It Should Work

**Session Flow:**
1. User says "practice" or "let's practice translations" (or the assistant proactively offers after adding cards)
2. Claude selects phrases based on the user's learning summary and recent card additions
3. Claude presents an English phrase, user attempts the Spanish translation
4. Claude provides detailed feedback, then moves to the next phrase
5. After a round (5-10 phrases), Claude gives a summary with score and areas to improve

**Phrase Selection Strategy (critical for effectiveness):**
- **70% recently added/reviewed words**: Draw from the user's vocabulary list in learning_summary.json
- **20% slightly above current level**: Use words from the "what_to_learn" gaps (i+1 comprehensible input)
- **10% consolidation**: Words the user has had for a while, mixed into more complex sentences

**Difficulty Progression (5 levels within each CEFR band):**
1. Single word/phrase translation: "the red book" -> "el libro rojo"
2. Simple sentence: "I run every morning" -> "Corro todas las mañanas"
3. Sentence with tense targeting: "Yesterday I ran five kilometers" -> "Ayer corrí cinco kilómetros"
4. Complex sentence: "If I had time, I would run more often" -> "Si tuviera tiempo, correría más seguido"
5. Contextual/conversational: "Tell your friend you can't come to the party because you're sick"

**Feedback Design:**
- Mark the translation as correct, partially correct, or incorrect
- For partially correct: highlight exactly what was right and what needs work
- Always show the model answer AND explain WHY
- Note common errors: false friends, ser/estar confusion, por/para, preterite/imperfect
- If the user makes the same type of error 2+ times, flag it as a pattern

---

## 2. GRAMMAR QUIZ / EXAM DESIGN

### Core Principle: Targeted Assessment, Not Random Testing

### Quiz Types (ordered by pedagogical value):

**Type 1: Fill-in-the-Blank Conjugation**
```
"Ayer yo _____ (correr) cinco kilómetros."
Answer: corrí
```

**Type 2: Choose the Correct Form (Multiple Choice)**
```
"Mi hermana _____ doctora."
a) es  b) está  c) ser  d) estar
Answer: a) es (permanent profession = ser)
```

**Type 3: Error Correction**
```
"Ayer yo estuve muy cansado todo el día."
What's wrong? -> Should be "estaba" (ongoing state in the past = imperfect)
```

**Type 4: Sentence Transformation**
```
Change to past tense: "Corro todas las mañanas"
-> "Corría todas las mañanas" (habitual = imperfect)
```

**Type 5: Free Production**
```
"Write a sentence using the subjunctive to express a wish"
-> "Ojalá que llueva mañana"
```

### Quiz Structure:
- **Quick Quiz (5 minutes):** 10 questions, ONE grammar topic
- **Level Assessment (15-20 minutes):** 25-30 questions, covers ALL grammar for a CEFR level
- **Comprehensive Exam (30+ minutes):** 50 questions across multiple levels

### Scoring:
- Per-topic scores: "Preterite: 90%, Imperfect: 65%, Ser/Estar: 80%"
- Below 70% = needs review, 70-85% = developing, above 85% = mastered

---

## 3. TOOL NOTES / USER PREFERENCES

### What Preferences Matter for Language Learning:

**Card Creation Preferences:**
- `example_count`: How many example sentences per card (default: 5)
- `include_conjugations`: Whether verb cards include conjugation tables
- `conjugation_tenses`: Which tenses to show
- `regional_variant`: Latin American vs Castilian Spanish
- `include_pronunciation_notes`: IPA or phonetic hints

**Learning Style Preferences:**
- `preferred_topics`: User's interests for examples (cooking, travel, technology)
- `formal_vs_informal`: Emphasize tú or usted forms
- `translation_direction`: EN->ES, ES->EN, or both
- `session_length`: Preferred number of practice/quiz items

**Feedback Preferences:**
- `feedback_detail`: "brief" vs "detailed"
- `encouragement_style`: "minimal" vs "encouraging"
- `error_tolerance`: How strictly to grade

---

## 4. IMPROVED PROGRESS TRACKING

### What to Add:

**A. Retention Rate Tracking**
- Pull Anki's review data (cards seen, remembered, forgotten, mature count)
- "You've added 276 cards, 180 are mature, 50 are in learning, 46 haven't been reviewed"

**B. Study Streak & Consistency**
- Track daily practice sessions
- Show streaks: "You've studied 12 days in a row"

**C. Skills Radar**
Track proficiency across multiple dimensions:
- Vocabulary breadth, Grammar accuracy, Productive skill, Topic coverage, Retention

**D. Time-Based Progress**
- Cards added per week/month
- CEFR coverage progression over time

**E. Weak Spots Dashboard**
- Grammar concepts with lowest scores
- Vocabulary areas with highest error rates
- Most-forgotten cards

---

## 5. ADDITIONAL FEATURES

### Feature A: Contextual Reading Practice
Claude presents a short paragraph using known vocabulary plus a few new words. User reads, answers comprehension questions, identifies new words.

### Feature B: Themed Vocabulary Expansion
Claude proactively suggests thematic word sets based on gaps.

### Feature C: Conversation Simulation
Claude plays a role (waiter, doctor, colleague) and the user responds in Spanish. Scenarios tied to CEFR levels.

### Feature D: Word of the Day / Daily Challenge
On session start: a new word from gap areas + quick review + mini translation exercise.

### Feature E: Error Journal
Persist common mistakes. Claude periodically reviews and offers targeted practice.

### Feature F: Spaced Review Integration
Pull "cards due today" and offer translation practice on those specific words.

---

## IMPLEMENTATION PRIORITY:

1. Translation Practice (highest impact)
2. Grammar Quizzes (second highest)
3. Improved Progress Tracking (motivational)
4. Tool Notes / Preferences (quality-of-life)
5. Conversation Simulation (high value, more complex)
6. Smaller features (incremental)
