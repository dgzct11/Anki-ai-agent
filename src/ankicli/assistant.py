"""Claude assistant with Anki tool calling."""

import json
import os
import queue
import time
from pathlib import Path
from typing import Generator

from anthropic import Anthropic
from dotenv import load_dotenv

# Load .env file from current directory or project root
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .client import AnkiClient, AnkiConnectError
from .config import load_config, get_model_specs
from .conversation_store import load_conversation, save_conversation
from .delegate import CardDelegateProcessor, ProgressEvent
from .learning_summary import load_summary
from .tool_handlers import HANDLERS
from .tools import ANKI_TOOLS

_CORE_IDENTITY = """You are an Anki flashcard assistant. You help users manage their Anki flashcard decks through conversation.

You can:
- List and browse decks
- Add new flashcards (single or bulk - use add_multiple_cards for efficiency)
- Edit existing cards (single or bulk)
- Delete cards
- Search cards and manage tags
- Move cards between decks
- Create new decks
- Sync with AnkiWeb"""

_CARD_FORMAT_GUIDE = """## Spanish Vocabulary Card Format

IMPORTANT: Anki uses HTML formatting. Always use HTML tags for formatting cards.

**Front (English):**
- The English definition/meaning
- Keep it clear and concise

**Back (Spanish):**
- The Spanish word (bold)
- For verbs: include conjugations in a clear format
- 5 example sentences showing the word in context
- Use a variety of tenses and conjugations in examples

Example for a verb:
Front: "to run"
Back:
<b>correr</b><br><br>
<b>Conjugation:</b><br>
• yo corro, tú corres, él corre<br>
• pretérito: corrí, corriste, corrió<br>
• imperfecto: corría<br><br>
<b>Examples:</b><br>
1. Corro todas las mañanas en el parque. <i>(present)</i><br>
2. Ayer corrí cinco kilómetros. <i>(preterite)</i><br>
3. Cuando era niño, corría muy rápido. <i>(imperfect)</i><br>
4. Mañana correré en la maratón. <i>(future)</i><br>
5. Si tuviera tiempo, correría más seguido. <i>(conditional)</i>

Example for a noun:
Front: "the book"
Back:
<b>el libro</b> <i>(m.)</i><br><br>
<b>Examples:</b><br>
1. El libro está en la mesa.<br>
2. Me regalaron un libro muy interesante.<br>
3. Los libros de esta biblioteca son antiguos.<br>
4. ¿Has leído este libro?<br>
5. Necesito comprar libros para la clase.

HTML tags to use:
- <b>bold</b> for the Spanish word and section headers
- <i>italic</i> for gender markers, tense labels, notes
- <br> for line breaks
- • for bullet points"""

_GENERAL_GUIDELINES = """## General Guidelines

When creating flashcards:
- For bulk operations, use add_multiple_cards to add many cards at once (10, 20, 50+ cards)
- Before adding, use find_cards_by_words (exact tag matching) to avoid duplicates
- Suggest tags when relevant (e.g., "verb", "noun", "adjective", "irregular")

CRITICAL tagging rule for word:: tags:
Every card MUST have exactly ONE word:: tag. This is how the system looks up cards.
Wrong tags = card not found = duplicates, broken practice, broken review.

Rules for the word:: tag value:
1. ALWAYS lowercase: word::correr (not word::Correr)
2. Multi-word phrases: use underscores for spaces
   word::tal_vez, word::sin_embargo, word::a_menudo, word::de_repente, word::a_pesar_de
   NEVER tag just one word of a phrase (word::vez for "tal vez" is WRONG)
3. Verbs: ALWAYS use the infinitive form
   word::correr (not word::corro/corrí/corriendo)
   word::tener (not word::tengo/tiene)
   Reflexive verbs: word::sentirse (not word::sentir or word::se_siente)
4. Adjectives: ALWAYS use masculine singular form
   word::bueno (not word::buena/buenos/buenas)
   word::junto (not word::juntos/junta/juntas)
   word::grande (no gender change, but not word::grandes)
5. Nouns: use singular form with article indicator in the card, but tag without article
   word::libro (not word::el_libro or word::libros)
   word::casa (not word::la_casa or word::casas)
6. Prepositions/conjunctions/adverbs: as-is
   word::pero, word::porque, word::siempre, word::bastante
7. Compound verbs / phrasal: include the full expression
   word::darse_cuenta, word::tener_que, word::ir_de_compras, word::hacer_falta
   NOT word::cuenta for "darse cuenta"

When editing cards:
- First search to find the cards and get their note IDs
- Use update_card for single edits or update_multiple_cards for bulk edits
- Always confirm before deleting cards

When the user wants to add cards, confirm the deck name first by listing available decks if needed.
Be helpful and proactive - if the user mentions a topic they're studying, offer to create relevant flashcards."""

_LEARNING_SUMMARY_GUIDE = """## Learning Summary (IMPORTANT)

AFTER successfully adding cards, you MUST call update_learning_summary to update the persistent progress tracker.

For each CEFR level (A1, A2, B1, B2), the summary tracks:
- **what_i_know**: Detailed description of mastered content, vocabulary list, grammar concepts learned, topics covered
- **what_to_learn**: What's still needed to complete the level, vocabulary gaps, grammar gaps, priority topics
- **estimated_coverage**: Percentage of level completion (0-100)

When calling update_learning_summary, provide:
1. The CEFR level (A1, A2, B1, B2)
2. Words added (list of Spanish words/phrases)
3. what_i_know_summary: A detailed text description of what the user now knows at this level
4. grammar_concepts_learned: Any grammar concepts practiced (e.g., "Preterite tense", "Reflexive verbs")
5. topics_covered: Topic areas covered (e.g., "Daily routines", "Travel", "Health")
6. what_to_learn_summary: Update what's still needed to complete this level
7. vocabulary_gaps, grammar_gaps, priority_topics: Lists of what to focus on next
8. estimated_coverage: Updated percentage (be realistic based on CEFR requirements)

This summary persists across sessions and helps track long-term progress.

When asked about progress or what to learn next, use get_learning_summary to review the current state."""

_CONTEXT_MANAGEMENT = """## Context Management

Monitor the context usage shown after each response. When context exceeds 50%, proactively use the compact_conversation tool to summarize older messages and free up space. This ensures the conversation can continue smoothly.

Keep responses concise and focused on the task at hand."""

_CEFR_GUIDE = """## CEFR Progress Tracking

You have access to CEFR (Common European Framework) vocabulary and grammar lists for Spanish (A1-C2).

Use these tools to give users concrete, data-driven progress:
- **get_cefr_progress**: Shows "142/500 A1 words known" with per-category breakdown
- **get_cefr_suggestions**: Suggests specific words to learn next based on gaps
- **sync_cefr_progress**: Full rescan of cards against CEFR lists (use after bulk changes)

When the user asks about progress, prefer get_cefr_progress over the older get_learning_summary for vocabulary metrics.

Auto-tagging: When cards are added with a word:: tag, CEFR level and theme tags (cefr::a1, theme::food_nutrition) are automatically added.

When suggesting what to learn next, use get_cefr_suggestions to give specific word recommendations from CEFR gaps."""

_PRACTICE_EVALUATION_GUIDE = """## Translation Practice Evaluation

When evaluating translations in practice mode (messages starting with [PRACTICE MODE]):

**Multi-Word Sentences (IMPORTANT for efficiency):**
Practice uses a two-step flow:
1. GENERATE: You receive a list of upcoming words. Generate a natural sentence that includes
   the primary target word PLUS 1-2 other words from the list that fit naturally.
   Do NOT reveal the target words to the user. Just present the sentence to translate.
2. EVALUATE: After the user translates, evaluate their work and give per-word feedback.

Example: If upcoming words include comprar, tienda, precio — generate:
"I bought a book at the store because the price was good."
The user must figure out which Spanish words to use without being told.

This tests productive recall, not recognition. NEVER show target words in the question.
NEVER tell the user which words you are testing, which words are due, or which words are coming up.
Do NOT say things like "Remaining due words: X, Y, Z" or "Let me use comprar and tienda".
The user must figure out which Spanish words to use entirely on their own.

**Scoring Rubric (0-4 for each):**
- **Meaning** (0-4): 0=completely wrong, 1=major errors, 2=partially correct, 3=correct with minor issues, 4=perfect
- **Grammar** (0-4): 0=incomprehensible, 1=major grammar errors, 2=some errors, 3=minor errors, 4=grammatically perfect
- **Naturalness** (0-4): 0=not natural at all, 1=understandable but awkward, 2=somewhat natural, 3=mostly natural, 4=sounds native
- **Vocabulary** (0-4): 0=wrong words, 1=poor word choices, 2=acceptable, 3=good vocabulary, 4=excellent/precise

**Response Format:**
Always include scores in this format: Meaning: X/4, Grammar: X/4, Naturalness: X/4, Vocabulary: X/4

**Accents/Tildes:**
The user is typing in a terminal where accents are difficult to type. Do NOT penalize missing
accents (manana = mañana, esta = está, el = él). Treat them as correct. Include the proper
accents in YOUR corrected version so the user can see the right spelling, but never mark
the user wrong or "partial" for missing accents alone.

**Feedback Guidelines:**
- Be encouraging but honest
- If incorrect, show the correct translation (with proper accents)
- Explain WHY something is wrong (grammar rule, vocabulary choice) — but not missing accents
- For partial answers, highlight what was good AND what needs improvement
- Adapt complexity: if user gets 3+ right, use more complex phrases; if 2+ wrong, simplify and explain grammar
- Give per-word feedback when testing multiple words: "comprar ✓, tienda ✓, precio ✗ (you used coste instead)"

**Anki Review (after session):**
After the practice session ends, use get_session_due_words to check which words are due.
Show a clean suggestion table of what to press in Anki. Do NOT try to mark cards programmatically."""

_ERROR_JOURNAL_GUIDE = """## Error Journal

You have access to a persistent error journal that tracks the user's recurring mistakes across practice and quiz sessions.

**When to log errors:**
- During translation practice: if the user makes a STRUCTURAL mistake, call log_error
- During grammar quizzes: if the user gets a question wrong, log the specific error pattern
- During conversation simulations: if you correct a structural mistake, log it

**What to log (structural/grammatical issues only):**
- verb_conjugation: wrong tense, person, or form (e.g., "corrí" vs "corría")
- ser_vs_estar: using the wrong "to be"
- por_vs_para: wrong preposition choice
- preposition_choice: other preposition errors (a/en/de/con)
- gender_agreement: wrong article or adjective gender
- article_usage: missing or wrong article (el/la/los/las/un/una)
- subjunctive_needed: indicative used where subjunctive is required
- preterite_vs_imperfect: wrong past tense
- word_order: incorrect sentence structure
- false_friend: used a false cognate incorrectly
- reflexive_verb: missing or wrong reflexive pronoun
- direct_vs_indirect_object: wrong object pronoun (lo/la/le)

**What NOT to log (ignore these):**
- Accent/tilde mistakes (día vs dia, qué vs que)
- Spelling errors or typos
- Capitalization issues
- Minor punctuation differences

**When to check errors:**
- At the start of practice/quiz sessions, call get_error_patterns to see what the user struggles with
- Use this to focus practice on weak areas
- Mention progress when a previously frequent error stops appearing

Do NOT over-log: only log genuine mistakes, not typos or one-off slips. Focus on patterns that appear 2+ times."""

_CONVERSATION_SIM_GUIDE = """## Conversation Simulation Mode

You can start role-play conversation simulations using start_conversation_sim. In conversation mode:

**Scenarios by CEFR level:**
- A2: ordering_food, asking_directions, hotel_checkin, shopping
- B1: job_interview, doctor_visit, phone_call, apartment_rental
- B2: debate, negotiation, complaint, storytelling

**During conversation (messages starting with [CONVERSATION MODE]):**
- Stay in character and speak Spanish (with parenthetical translations at A2)
- Keep responses to 2-4 sentences
- Gently correct mistakes in-character
- Call log_error for recurring mistake patterns
- After the conversation ends, summarize performance and offer to create Anki cards for new vocabulary
- If practiced words are due for Anki review, ASK the user before marking them

When the user asks to practice conversation or role-play, use start_conversation_sim."""

_DAILY_CHALLENGE_GUIDE = """## Word of the Day / Daily Challenge

At the start of each new session, call get_daily_challenge to offer the user a word of the day.
The challenge picks a word from their CEFR gap areas and provides:
1. The word with pronunciation tips
2. Example sentences
3. A quick translation exercise
4. An offer to create an Anki card

Keep it brief (2-3 minutes). Only present once per day unless the user asks for a new one.
If the user declines, move on without insisting."""

_STUDY_SUGGESTIONS_GUIDE = """## Smart Study Suggestions

Use get_study_suggestion to give personalized recommendations based on:
- Cards due today (review first before new material)
- Weakest CEFR level and category
- Recurring error patterns from the error journal
- Recent quiz performance

Call this at the start of a session or when the user asks "what should I study?" to provide data-driven advice."""

_VOCAB_NETWORK_GUIDE = """## Vocabulary Network (V1-V11)

Build vocabulary networks, not isolated flashcards. After adding a card:

**V1 - Connection discovery:** Call update_word_network to store connections (synonyms, antonyms,
morphological family, collocations, thematic links, confusables). Use show_word_connections to display them.

**V3 - Morphological families:** Use get_morphological_family to find word relatives (-cion, -mente,
-dor, -able, des-, re-). IMPORTANT: After adding ANY card, the tool will show related word family
members not yet in the deck. Always ask the user if they want to add those related words too
(e.g. "I see 'educación' is related to 'educar'. Want me to add 'educador' and 'educable' too?").

**V4 - Disambiguation practice:** Use get_disambiguation_practice for confusable pairs (ser/estar,
por/para, saber/conocer). INTERNAL practice mode, not Anki cards. Use show_disambiguation_pairs to list all.
After practice, call log_disambiguation_result to track progress.

**V5 - Collocations:** Include important collocations on card backs when adding cards. Store them via
update_word_network with the collocations parameter.

**V6 - False friend alerts:** When adding a word, check against known false friends (check_false_friend).
Add warnings to the card if detected.

**V7 - Network-aware sentences:** During translation practice, include 2-3 related words from the network
in practice sentences to reinforce connections.

**V8 - Pair-based review:** Use start_pair_review for comparative practice of antonym/contrast pairs.
INTERNAL mode, not Anki cards.

**V9 - Semantic field progress:** Use get_semantic_field_progress to show vocabulary coverage per theme
(food, travel, health, etc.) from CEFR data.

**V10 - Connection map:** Use show_connection_map for an on-demand ASCII visualization of a word's network.

**V11 - Spaced network activation:** Use get_network_study_suggestions to suggest words connected to
recently-reviewed words, reinforcing vocabulary clusters.

When to use get_related_words vs the network:
- get_related_words: For CEFR-based semantic suggestions (same category/subcategory)
- show_word_connections: For stored network connections (explicit relationships you've built)
- get_morphological_family: For derivation patterns (suffixes/prefixes)"""

_CONTEXTUAL_SENTENCES_GUIDE = """## Contextual Sentence Generator

Use generate_contexts to create example sentences for a word in specific contexts:
- "conversation": casual spoken dialogue
- "formal": business/official communication
- "narrative": storytelling, literature
- "email": correspondence
- "academic": essays, reports

Use this when:
- Enriching an existing card with more examples
- The user wants to see a word used in different registers
- Creating cards that show real-world usage patterns"""

_COGNATE_GUIDE = """## Cognate Hints on Card Backs (C1)

When creating flashcards for Spanish vocabulary, include a cognate hint line on the card back
when it would aid memorization. Use this HTML format at the end of the card back:

<br><hr style="border:0;border-top:1px solid #ccc;margin:8px 0">
<span style="color:#666;font-size:0.9em">cf. FR <i>word</i> / RO <i>word</i> / EN <i>word</i> — from Latin <i>root</i></span>

Guidelines:
- Include French (FR), Romanian (RO), and/or English (EN) cognates when they help memory
- Add the Latin root when it illuminates the connection
- Skip obvious transparent cognates (restaurante/restaurant, hotel/hotel) — no hint needed
- Skip when there is no useful cognate connection
- Examples of when to include:
  - "biblioteca" -> cf. FR bibliothèque / EN bibliography — from Greek bibliotheke
  - "hablar" -> cf. FR parler / RO a vorbi — from Latin fabulare (to tell stories)
  - "comprar" -> cf. FR acheter / EN compare — from Latin comparare"""

_FALSE_FRIENDS_GUIDE = """## False Friend Warnings (C2)

CRITICAL: When creating or showing cards for known false friends, add a prominent warning.
Use this HTML format on the card back, placed right after the Spanish word:

<div style="background:#fff3f3;border-left:4px solid #e74c3c;padding:6px 10px;margin:8px 0;font-size:0.95em">
<b style="color:#e74c3c">False Friend Warning:</b> <i>warning text</i>
</div>

The ~20 critical Spanish-English false friends you MUST flag:
- embarazada = pregnant (NOT embarrassed; avergonzado = embarrassed)
- éxito = success (NOT exit; salida = exit)
- carpeta = folder (NOT carpet; alfombra = carpet)
- actual = current (NOT actual; real/verdadero = actual)
- realizar = to carry out (NOT to realize; darse cuenta = to realize)
- asistir = to attend (NOT to assist; ayudar = to assist)
- sensible = sensitive (NOT sensible; sensato = sensible)
- molestar = to bother (NOT to molest; abusar = to molest)
- constipado = having a cold (NOT constipated; estreñido = constipated)
- librería = bookstore (NOT library; biblioteca = library)
- fábrica = factory (NOT fabric; tela = fabric)
- recordar = to remember (NOT to record; grabar = to record)
- soportar = to endure (NOT to support; apoyar = to support)
- largo = long (NOT large; grande = large)
- suceso = event (NOT success; éxito = success)
- contestar = to answer (NOT to contest; competir = to contest)
- introducir = to insert (NOT to introduce someone; presentar = to introduce)
- compromiso = commitment (NOT compromise; acuerdo mutuo = compromise)
- pretender = to try/aspire (NOT to pretend; fingir = to pretend)
- ropa = clothing (NOT rope; cuerda = rope)

Always check if a word is a false friend before creating a card. When found, the warning is mandatory."""

_ETYMOLOGY_DISAMBIGUATION_GUIDE = """## Etymology for Disambiguation (C3)

When explaining commonly confused word pairs, use Latin etymology as a memory anchor.
Include this as part of your explanation when the user encounters these pairs:

**ser vs estar:**
- ser < Latin sedere (to sit, to be settled) = permanent/essential traits
- estar < Latin stare (to stand, temporary state) = temporary conditions, location
- Mnemonic: "SER = settled/permanent. ESTAR = standing in a temporary state."

**por vs para:**
- por < Latin pro (on behalf of, because of) = cause, exchange, duration, through
- para < Latin per ad (through toward) = purpose, destination, deadline, recipient
- Mnemonic: "POR = the reason behind. PARA = the goal ahead."

**saber vs conocer:**
- saber < Latin sapere (to taste, to have wisdom) = facts, information, how-to
- conocer < Latin cognoscere (to become acquainted) = people, places, familiarity
- Mnemonic: "SABER = tasting knowledge/facts. CONOCER = getting to know."

**pedir vs preguntar:**
- pedir < Latin petere (to seek, request) = to request/ask for something
- preguntar < Latin percontari (to inquire) = to ask a question
- Mnemonic: "PEDIR = request something. PREGUNTAR = ask a question."

**llevar vs traer:**
- llevar < Latin levare (to lift, carry away) = to take away from here
- traer < Latin trahere (to pull toward) = to bring toward here
- Mnemonic: "LLEVAR = carry away. TRAER = bring here."

Use these etymologies whenever explaining these pairs in practice, quizzes, or card creation.
When creating cards for these words, include the Latin root on the card back."""

_TOOL_NOTES_GUIDE = """## User Preferences (Tool Notes)

You can save and manage user preferences using the set_tool_note, get_tool_notes, and remove_tool_note tools.

When the user expresses a preference about how cards should be created or how you should behave, proactively offer to save it as a tool note so it persists across sessions. Examples:
- "I prefer informal Spanish" -> offer to save as general note
- "Use 3 examples instead of 5" -> offer to save for add_card/add_multiple_cards
- "Always use Latin American Spanish" -> offer to save as general note
- "I don't need conjugation tables for adjectives" -> offer to save for card creation

Always check and follow any saved preferences when performing actions."""

_PREFERENCE_DETECTION_GUIDE = """## Proactive Preference Detection

Watch for implicit preferences the user reveals through repeated behavior or casual comments. If you notice a pattern appearing 2-3 times, offer to save it as a persistent preference.

Patterns to watch for:
- **Card style**: "Can you make it shorter?" / always asking for fewer examples -> offer to set example count
- **Language variant**: User consistently uses Latin American vocab / avoids vosotros -> offer to set dialect preference
- **Formality**: User prefers tu over usted, casual over formal examples -> offer to note formality level
- **Correction style**: "Just tell me the answer" / "Explain more" -> offer to save feedback verbosity preference
- **Study habits**: User always practices at certain times, prefers certain topics -> note for study suggestions
- **Card content**: User always asks for pronunciation, etymology, or mnemonics -> offer to include by default

When you detect a pattern, say something like:
"I notice you consistently prefer [X]. Would you like me to save this as a preference so I always do this automatically?"

Then use set_tool_note to save it. Be specific in the saved note so future sessions respect it exactly."""

_MICRO_LESSON_GUIDE = """## Error Pattern Micro-Lessons

When you check the error journal (get_error_patterns) and find an error type with 3 or more occurrences, proactively offer a targeted micro-lesson using generate_micro_lesson.

Micro-lesson format (2-3 minutes):
1. Name the grammar rule clearly
2. Show the rule with 2-3 correct examples
3. Show the common mistake vs correct form (using the user's actual errors from the journal)
4. Quick practice: 3 fill-in-the-blank exercises
5. Offer to create Anki cards for the rule

Trigger this at the start of a practice session or when the user asks "what should I work on?"
Do not repeat a micro-lesson for the same error type within the same session."""

_GRAMMAR_QUIZ_GUIDE = """## Grammar Quiz Mode

You can start grammar quizzes using the start_grammar_quiz tool. The quiz system:
- Generates questions dynamically based on CEFR level and grammar topic
- Supports 5 question types: fill-in-the-blank, multiple choice, conjugation table, error correction, sentence transformation
- Supports 3 sizes: quick (10q), assessment (25-30q), comprehensive (50q) via --size parameter
- Tracks mastery per topic (>85% = mastered)
- Tracks per-topic grammar scores across sessions (get_grammar_scores tool)
- After a quiz, offers to create Anki cards for weak areas

When presenting quiz questions (messages starting with [QUIZ SESSION]):
- Present one question at a time in a clear format
- Do NOT reveal the answer until the user responds
- After each answer, provide grammar feedback with the rule explanation
- Use the log_quiz_results tool after the quiz ends to save results
- Track errors within the session - if same error type occurs 2+ times, flag it prominently

## Structured Quiz Flow (A3)

For assessment and comprehensive quizzes, follow this 5-step structure:
1. **Warm-up** (20% of questions): Review known grammar with easy questions to build confidence
2. **Teach concept** (brief): Before the main practice, give a 2-sentence explanation of the target grammar rule
3. **Practice** (50% of questions): Focus on the target concept with increasing difficulty
4. **Mixed review** (30% of questions): Mix the target concept with other related grammar
5. **Summary**: Score breakdown, weak areas, specific study recommendations

For quick quizzes, skip the warm-up and go straight to practice.

When the user asks to practice grammar or take a quiz, use start_grammar_quiz.
Use get_learning_summary to check grammar gaps and recommend topics."""

_ADAPTIVE_DIFFICULTY_GUIDE = """## Adaptive Difficulty (A2)

During translation practice, adapt sentence complexity based on user performance:

**5 Difficulty Levels per CEFR band:**
1. Single word translation (easiest)
2. Simple sentence (subject + verb + object)
3. Tense-targeted sentence (specific conjugation focus)
4. Complex sentence (subordinate clauses, multiple tenses)
5. Conversational context (idioms, colloquial expressions)

**Adaptation rules:**
- Start at level 2 (simple sentence)
- After 3+ correct in a row: increase difficulty by 1 level
- After 2+ wrong in a row: decrease difficulty by 1 level
- Never go below level 1 or above level 5
- When increasing difficulty, tell the user: "Great streak! Trying something harder..."
- When decreasing difficulty, tell the user: "Let's review the basics for this one."

Track the current difficulty level in your responses and mention level changes."""

_ANKI_REVIEW_INTEGRATION_GUIDE = """## Anki Review Integration (P11)

After ANY practice session is complete, show the user which words are due for Anki review.

Steps:
1. Use get_session_due_words with session_results mapping each word to performance
2. Present a review table with suggested ratings and intervals
3. Ask user to confirm ratings (they can override)
4. Use mark_cards_reviewed to try marking them. It uses Anki's native answerCards API.
   Some cards may succeed, some may not (depends on Anki's internal queue state).
5. For any cards that couldn't be marked, show: "Review [word] in Anki → press [button]"

Present results cleanly:
  Marked in Anki:
    comprar → Good (next review ~10 days)
  Review these in Anki manually:
    salir → press Good (~8 days)
    vender → press Hard (~4 days)

IMPORTANT: ALWAYS refer to cards by their SPANISH WORD, never "this card".
IMPORTANT: Only call get_session_due_words AFTER the practice session is complete,
never during the session — the tool result shows Spanish words which would spoil answers."""

_READING_PRACTICE_GUIDE = """## Reading Practice (P9)

Use start_reading_practice to generate reading-only content. This is purely for vocabulary exposure:
- Claude generates a 100-150 word paragraph using the user's known vocabulary + review words
- NO testing, NO comprehension questions, NO translation requests
- Present in a Rich panel for pleasant reading
- Include a vocabulary glossary for unfamiliar words
- End with encouragement

Use when the user says "I want to read" or "reading practice" or when suggesting variety in study activities."""

_SESSION_ERROR_TRACKING_GUIDE = """## Within-Session Error Tracking (P10)

During practice and quiz sessions, track error patterns within the current session:
- If the same error type (gender_agreement, ser_vs_estar, etc.) occurs 2+ times in the session, flag it prominently
- Use format: "Pattern detected: you're consistently confusing [X]. [Brief explanation of the rule]."
- After flagging, offer a quick targeted exercise on that specific pattern
- At session end, include flagged patterns in the summary
- Also log these patterns to the persistent error journal using log_error"""

_VOCAB_LIST_GUIDE = """## Vocab Staging List

The user has a vocab list where they can save words they might want to add to their Anki deck later.

When to suggest adding to the vocab list (use add_to_vocab_list):
- When the user encounters a new word during practice/conversation that isn't in their deck
- When you suggest related words or cognates they might want to learn
- When the word-of-the-day or network suggestions surface interesting words
- When the user says "save that word" or "remind me about that word"

When to show the list (use get_vocab_list):
- When the user asks "what words do I have saved?" or "show my vocab list"
- At the start of a session, mention if there are words waiting: "You have 5 words on your vocab list"

When to remove from the list (use remove_from_vocab_list):
- After successfully creating an Anki card for a word from the list
- When the user explicitly says to remove a word

Always include the English translation and context when adding. Include CEFR level if known."""

# All prompt sections in order, for build_system_prompt to assemble.
_PROMPT_SECTIONS = [
    _CORE_IDENTITY,
    _CARD_FORMAT_GUIDE,
    _GENERAL_GUIDELINES,
    _LEARNING_SUMMARY_GUIDE,
    _CEFR_GUIDE,
    _PRACTICE_EVALUATION_GUIDE,
    _GRAMMAR_QUIZ_GUIDE,
    _CONVERSATION_SIM_GUIDE,
    _ERROR_JOURNAL_GUIDE,
    _DAILY_CHALLENGE_GUIDE,
    _STUDY_SUGGESTIONS_GUIDE,
    _VOCAB_NETWORK_GUIDE,
    _CONTEXTUAL_SENTENCES_GUIDE,
    _CONTEXT_MANAGEMENT,
    _COGNATE_GUIDE,
    _FALSE_FRIENDS_GUIDE,
    _ETYMOLOGY_DISAMBIGUATION_GUIDE,
    _TOOL_NOTES_GUIDE,
    _PREFERENCE_DETECTION_GUIDE,
    _MICRO_LESSON_GUIDE,
    _ADAPTIVE_DIFFICULTY_GUIDE,
    _ANKI_REVIEW_INTEGRATION_GUIDE,
    _READING_PRACTICE_GUIDE,
    _SESSION_ERROR_TRACKING_GUIDE,
    _VOCAB_LIST_GUIDE,
]


def build_student_context() -> str | None:
    """Build a dynamic student context section from CEFR progress, quiz scores,
    error journal, and difficulty tags.

    Returns the formatted section string, or None if no data is available.
    """
    from .cefr import load_progress_cache, LEVELS
    from .error_journal import get_error_patterns
    from .learning_summary import load_summary

    lines = ["## Your Current Student"]
    has_data = False

    # CEFR level progress
    progress = load_progress_cache()
    if progress:
        level_parts = []
        for lv in LEVELS:
            lp = progress.get(lv)
            if lp and lp.words_total > 0:
                level_parts.append(f"{lv} ({lp.percent:.0f}%)")
        if level_parts:
            lines.append(f"- Active level: {' / '.join(level_parts)}")
            has_data = True

    # Learning summary - grammar and topics
    try:
        summary = load_summary()
        total_cards = summary.get("total_cards_added", 0)
        if total_cards > 0:
            lines.append(f"- {total_cards} cards total")
            has_data = True

        last_updated = summary.get("last_updated", "")
        if last_updated:
            lines.append(f"- Last session: {last_updated[:10]}")

        # Gather strong areas (grammar concepts from levels with >50% coverage)
        strong_areas = []
        weak_areas = []
        levels_data = summary.get("levels", {})
        for lv in ("A1", "A2", "B1", "B2"):
            level_data = levels_data.get(lv, {})
            coverage = level_data.get("estimated_coverage", 0)
            grammar = level_data.get("what_i_know", {}).get("grammar_concepts", [])
            grammar_gaps = level_data.get("what_to_learn", {}).get("grammar_gaps", [])
            if coverage >= 50:
                strong_areas.extend(grammar[:3])
            weak_areas.extend(grammar_gaps[:2])

        if strong_areas:
            lines.append(f"- Strong areas: {', '.join(strong_areas[:5])}")
            has_data = True
        if weak_areas:
            lines.append(f"- Weak areas: {', '.join(weak_areas[:5])}")
            has_data = True

        # Quiz score summary
        quiz_results = summary.get("quiz_results", [])
        if quiz_results:
            recent = quiz_results[-5:]
            avg_score = sum(q.get("score", 0) for q in recent) / len(recent)
            lines.append(f"- Recent quiz avg: {avg_score:.0f}% (last {len(recent)} quizzes)")
            has_data = True

        # Practice session stats
        practice_sessions = summary.get("practice_sessions", [])
        if practice_sessions:
            recent_practice = practice_sessions[-3:]
            avg_practice = sum(p.get("score_percent", 0) for p in recent_practice) / len(recent_practice)
            lines.append(f"- Recent practice avg: {avg_practice:.0f}% (last {len(recent_practice)} sessions)")
            has_data = True
    except Exception:
        pass

    # Error patterns
    try:
        errors = get_error_patterns(min_count=2, limit=5)
        if errors:
            error_summary = ", ".join(f"{e.error_type} (x{e.count})" for e in errors[:3])
            lines.append(f"- Recurring errors: {error_summary}")
            has_data = True
    except Exception:
        pass

    # Difficulty distribution from CEFR categories
    if progress:
        try:
            difficulty_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            total_known = 0
            for lv_idx, lv in enumerate(LEVELS, 1):
                lp = progress.get(lv)
                if lp and lp.words_known > 0:
                    bucket = min(lv_idx, 5)
                    difficulty_counts[bucket] += lp.words_known
                    total_known += lp.words_known
            if total_known > 0:
                dist_parts = []
                for d in range(1, 6):
                    pct = difficulty_counts[d] / total_known * 100
                    if pct > 0:
                        dist_parts.append(f"{d}:{pct:.0f}%")
                if dist_parts:
                    lines.append(f"- Difficulty distribution: {' '.join(dist_parts)}")
                    has_data = True
        except Exception:
            pass

    if not has_data:
        return None

    return "\n".join(lines)


def build_system_prompt(*, general_note: str | None = None, extra_sections: list[str] | None = None, student_context: str | None = None) -> str:
    """Assemble the system prompt from composable sections.

    Args:
        general_note: User-set general preference note (injected at end).
        extra_sections: Additional prompt sections to append (e.g. CEFR guide).
        student_context: Dynamic student context section (from build_student_context).
    """
    sections = list(_PROMPT_SECTIONS)
    if extra_sections:
        sections.extend(extra_sections)
    prompt = "\n\n".join(sections)
    if student_context:
        prompt += f"\n\n{student_context}"
    if general_note:
        prompt += f"\n\n## Active User Preferences\n\nIMPORTANT - The user has set these global preferences. Always follow them:\n{general_note}"

    # Inject due reminders
    try:
        from datetime import datetime
        from .tool_handlers import _load_reminders
        reminders = _load_reminders()
        now = datetime.now()
        due = [r for r in reminders if datetime.fromisoformat(r.get("remind_at", "9999-12-31")) <= now]
        if due:
            lines = ["## Active Reminders", "", "You have reminders that are now due. Mention these to the user:"]
            for r in due:
                rid = r.get("id", "?")
                msg = r.get("message", "?")
                remind_at = datetime.fromisoformat(r["remind_at"])
                time_label = remind_at.strftime("%b %d %I:%M %p")
                lines.append(f"- [{rid}] \"{msg}\" (was set for {time_label})")
            prompt += "\n\n" + "\n".join(lines)
    except Exception:
        pass  # Don't break the prompt if reminders fail to load

    return prompt


class AnkiAssistant:
    """Claude-powered Anki assistant with tool calling."""

    def __init__(self, model: str | None = None, stateless: bool = False):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your API key from https://console.anthropic.com/"
            )

        self.stateless = stateless
        if stateless:
            from .config import Config
            self.config = Config()  # Empty default config, no file I/O
        else:
            self.config = load_config()
        self.client = Anthropic(api_key=api_key)
        self.anki = AnkiClient()
        self.model = model or self.config.main_model
        self._model_specs = get_model_specs(self.model)
        self.messages: list[dict] = []
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        self._auto_save = not stateless  # Disable auto-save in stateless mode
        self._progress_queue: queue.Queue[dict] = queue.Queue()
        # Session tracking
        self.session_start_time = time.time()
        self.session_cards_added = 0

    def _get_tools_with_notes(self) -> list[dict]:
        """Return tools list with user preference notes injected into descriptions."""
        tools = []
        for tool in ANKI_TOOLS:
            note = self.config.tool_notes.get(tool["name"])
            if note:
                tool_copy = {**tool}
                tool_copy["description"] = tool["description"] + f"\n\nUSER PREFERENCE: {note}"
                tools.append(tool_copy)
            else:
                tools.append(tool)
        return tools

    def _get_system_prompt(self) -> str:
        """Return system prompt with user preferences and student context injected."""
        try:
            student_ctx = build_student_context()
        except Exception:
            student_ctx = None
        return build_system_prompt(
            general_note=self.config.tool_notes.get("general"),
            student_context=student_ctx,
        )

    @property
    def max_context_tokens(self) -> int:
        """Context window size for the current model."""
        return self._model_specs["context_window"]

    @property
    def max_output_tokens(self) -> int:
        """Maximum output tokens for the current model."""
        return self._model_specs["max_output_tokens"]

    @property
    def model_name(self) -> str:
        """Human-readable name for the current model."""
        return self._model_specs["name"]

    @property
    def total_tokens_used(self) -> int:
        """Total tokens used in the conversation."""
        return self.input_tokens_used + self.output_tokens_used

    @property
    def context_usage_percent(self) -> float:
        """Percentage of context window used."""
        return (self.input_tokens_used / self.max_context_tokens) * 100

    def get_context_status(self) -> dict:
        """Get current context usage status."""
        elapsed = time.time() - self.session_start_time
        session_minutes = int(elapsed / 60)
        return {
            "input_tokens": self.input_tokens_used,
            "output_tokens": self.output_tokens_used,
            "total_tokens": self.total_tokens_used,
            "max_tokens": self.max_context_tokens,
            "percent_used": self.context_usage_percent,
            "model": self.model,
            "model_name": self.model_name,
            "session_minutes": session_minutes,
            "session_cards_added": self.session_cards_added,
        }

    def load_from_disk(self) -> bool:
        """
        Load conversation from disk.

        Returns:
            True if conversation was loaded, False if starting fresh
        """
        data = load_conversation()
        if data["messages"]:
            self.messages = data["messages"]
            self.input_tokens_used = data["input_tokens"]
            self.output_tokens_used = data["output_tokens"]
            return True
        return False

    def save_to_disk(self) -> None:
        """Save current conversation to disk."""
        save_conversation(
            self.messages,
            self.input_tokens_used,
            self.output_tokens_used
        )

    def _auto_save_if_enabled(self) -> None:
        """Auto-save if enabled."""
        if self._auto_save:
            self.save_to_disk()

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute an Anki tool and return the result."""
        try:
            handler_fn = HANDLERS.get(tool_name)
            if handler_fn is None:
                return f"Unknown tool: {tool_name}"
            return handler_fn(
                self.anki,
                tool_input,
                config=self.config,
                assistant=self,
            )
        except AnkiConnectError as e:
            return f"Anki error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _run_delegate(self, cards: list, prompt: str, source_label: str,
                      workers: int, dry_run: bool) -> str:
        """Run the delegate processor on a list of cards and return a summary.

        Shared implementation for both all_cards_delegate and card_subset_delegate.
        """
        processor = CardDelegateProcessor(
            client=self.client,
            model=self.config.subagent_model,
            max_workers=workers,
            rate_limit_delay=self.config.delegate_rate_limit_delay,
        )

        def progress_callback(event: ProgressEvent) -> None:
            self._progress_queue.put({
                "type": "delegate_progress",
                "completed": event.completed,
                "total": event.total,
                "current_card": event.current_card,
                "success": event.success,
                "error": event.error,
            })

        results = processor.process_cards(cards, prompt, progress_callback)

        changed = [r for r in results if r.changed]
        errors = [r for r in results if r.error]

        summary_parts = [
            f"Processed {len(results)} cards{source_label}",
            f"Changed: {len(changed)}, Errors: {len(errors)}",
        ]

        if dry_run:
            summary_parts.insert(0, "[DRY RUN - No changes applied]")
            if changed:
                summary_parts.append("\nPreview of changes:")
                for r in changed[:5]:
                    summary_parts.append(f"\n- Card {r.note_id}:")
                    if r.transformed_front:
                        summary_parts.append(f"  Front: {r.transformed_front[:50]}...")
                    if r.transformed_back:
                        summary_parts.append(f"  Back: {r.transformed_back[:50]}...")
                    if r.reasoning:
                        summary_parts.append(f"  Reason: {r.reasoning}")
                if len(changed) > 5:
                    summary_parts.append(f"\n... and {len(changed) - 5} more changes")
        else:
            applied = 0
            for r in changed:
                try:
                    self.anki.update_note(
                        note_id=int(r.note_id),
                        front=r.transformed_front,
                        back=r.transformed_back,
                        tags=r.transformed_tags,
                    )
                    applied += 1
                except Exception as e:
                    errors.append(r)
            summary_parts.append(f"Applied: {applied}")

        if errors:
            summary_parts.append(f"\nErrors:")
            for r in errors[:3]:
                summary_parts.append(f"- Card {r.note_id}: {r.error}")
            if len(errors) > 3:
                summary_parts.append(f"... and {len(errors) - 3} more errors")

        return "\n".join(summary_parts)

    def _handle_all_cards_delegate(self, tool_input: dict) -> str:
        """Handle the all_cards_delegate tool."""
        deck_name = tool_input["deck_name"]
        limit = tool_input.get("limit")
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)

        cards = self.anki.get_deck_cards(deck_name, limit=limit or 1000)
        if not cards:
            return f"No cards found in deck '{deck_name}'"
        if limit:
            cards = cards[:limit]

        return self._run_delegate(
            cards, tool_input["prompt"], f" from '{deck_name}'",
            workers, tool_input.get("dry_run", False),
        )

    def _handle_card_subset_delegate(self, tool_input: dict) -> str:
        """Handle the card_subset_delegate tool."""
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)

        cards = []
        for note_id in tool_input["note_ids"]:
            card = self.anki.get_note(note_id)
            if card:
                cards.append(card)

        if not cards:
            return "No cards found for the given note IDs"

        return self._run_delegate(
            cards, tool_input["prompt"], "",
            workers, tool_input.get("dry_run", False),
        )

    def _fix_conversation_state(self) -> None:
        """Fix conversation state if there are orphaned tool_use or tool_result blocks."""
        if not self.messages:
            return

        # Helper to get tool_use IDs from a message
        def get_tool_use_ids(content) -> set:
            ids = set()
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        ids.add(block.id)
                    elif isinstance(block, dict) and block.get("type") == "tool_use":
                        ids.add(block.get("id"))
            return ids

        # Helper to get tool_result IDs from a message
        def get_tool_result_ids(content) -> set:
            ids = set()
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        ids.add(block.get("tool_use_id"))
            return ids

        # Scan through messages and validate tool_use/tool_result pairs
        i = 0
        while i < len(self.messages):
            msg = self.messages[i]

            # Check for assistant messages with tool_use
            if msg["role"] == "assistant":
                tool_use_ids = get_tool_use_ids(msg.get("content", []))

                if tool_use_ids:
                    # Must have a following user message with matching tool_results
                    if i + 1 >= len(self.messages):
                        # No following message, truncate here
                        self.messages = self.messages[:i]
                        return

                    next_msg = self.messages[i + 1]
                    if next_msg["role"] != "user":
                        # Next message isn't user, truncate
                        self.messages = self.messages[:i]
                        return

                    tool_result_ids = get_tool_result_ids(next_msg.get("content", []))

                    # Check if IDs match
                    if tool_use_ids != tool_result_ids:
                        # Mismatch - truncate conversation at this point
                        self.messages = self.messages[:i]
                        return

            # Check for user messages with tool_result (must follow assistant with tool_use)
            elif msg["role"] == "user":
                tool_result_ids = get_tool_result_ids(msg.get("content", []))

                if tool_result_ids:
                    # Must have a preceding assistant message with matching tool_use
                    if i == 0:
                        # No preceding message, remove this message
                        self.messages = self.messages[1:]
                        continue

                    prev_msg = self.messages[i - 1]
                    if prev_msg["role"] != "assistant":
                        # Previous isn't assistant, truncate before this
                        self.messages = self.messages[:i]
                        return

                    tool_use_ids = get_tool_use_ids(prev_msg.get("content", []))

                    if tool_use_ids != tool_result_ids:
                        # Mismatch - truncate before this tool_result message
                        self.messages = self.messages[:i]
                        return

            i += 1

    def chat(self, user_message: str) -> Generator[dict, None, None]:
        """
        Send a message and yield response events.

        Yields dicts with 'type' and 'content':
        - {"type": "text", "content": "..."}
        - {"type": "tool_use", "name": "...", "input": {...}}
        - {"type": "tool_result", "name": "...", "result": "..."}
        """
        # Fix any corrupted conversation state before adding new message
        self._fix_conversation_state()
        self.messages.append({"role": "user", "content": user_message})

        while True:
            # Stream the response
            collected_text = ""
            tool_uses = []

            try:
                stream_ctx = self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_output_tokens,
                    system=self._get_system_prompt(),
                    tools=self._get_tools_with_notes(),
                    messages=self.messages,
                )
            except Exception as e:
                error_str = str(e)
                if "tool_use" in error_str and "tool_result" in error_str:
                    # Conversation state is corrupted, try to fix it
                    yield {"type": "error", "content": "Recovering from corrupted conversation state..."}

                    # Remove the user message we just added
                    if self.messages and self.messages[-1]["role"] == "user":
                        self.messages.pop()

                    # Aggressively fix the conversation
                    self._fix_conversation_state()

                    # If still having issues, try removing more messages
                    if len(self.messages) > 2:
                        # Keep removing last message pair until we have a clean state
                        while len(self.messages) > 0:
                            try:
                                # Test if state is valid by trying a minimal API call
                                test_messages = self.messages + [{"role": "user", "content": "test"}]
                                # Just validate, don't actually call
                                break
                            except Exception:
                                # Remove last message and try again
                                self.messages.pop()

                    # Re-add user message and retry
                    self.messages.append({"role": "user", "content": user_message})
                    self._auto_save_if_enabled()
                    continue
                raise

            with stream_ctx as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_start":
                            if hasattr(event, "content_block"):
                                if event.content_block.type == "tool_use":
                                    tool_uses.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input": ""
                                    })
                        elif event.type == "content_block_delta":
                            if hasattr(event, "delta"):
                                if hasattr(event.delta, "text"):
                                    collected_text += event.delta.text
                                    yield {"type": "text_delta", "content": event.delta.text}
                                elif hasattr(event.delta, "partial_json"):
                                    if tool_uses:
                                        tool_uses[-1]["input"] += event.delta.partial_json

            # Get the final message
            response = stream.get_final_message()

            # Track token usage
            if hasattr(response, "usage"):
                self.input_tokens_used = response.usage.input_tokens
                self.output_tokens_used += response.usage.output_tokens

            # Yield context status update
            yield {"type": "context_status", "status": self.get_context_status()}

            # Add assistant response to messages
            self.messages.append({"role": "assistant", "content": response.content})

            # Check if we need to execute tools
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        yield {
                            "type": "tool_use",
                            "name": block.name,
                            "input": block.input
                        }

                        # For delegate tools, yield progress events during execution
                        is_delegate_tool = block.name in (
                            "all_cards_delegate",
                            "card_subset_delegate",
                        )

                        if is_delegate_tool:
                            # Clear the queue before starting
                            while not self._progress_queue.empty():
                                try:
                                    self._progress_queue.get_nowait()
                                except queue.Empty:
                                    break

                            # Execute in a way that allows yielding progress
                            import threading

                            result_holder: list[str] = []

                            def run_tool():
                                result_holder.append(
                                    self._execute_tool(block.name, block.input)
                                )

                            thread = threading.Thread(target=run_tool)
                            thread.start()

                            # Poll for progress events while tool runs
                            while thread.is_alive():
                                try:
                                    progress_event = self._progress_queue.get(timeout=0.1)
                                    yield progress_event
                                except queue.Empty:
                                    continue

                            thread.join()

                            # Drain remaining progress events
                            while not self._progress_queue.empty():
                                try:
                                    yield self._progress_queue.get_nowait()
                                except queue.Empty:
                                    break

                            result = result_holder[0] if result_holder else "Error: Tool execution failed"
                        else:
                            # Execute the tool normally
                            result = self._execute_tool(block.name, block.input)

                        yield {
                            "type": "tool_result",
                            "name": block.name,
                            "result": result
                        }

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                # Add tool results to messages and continue
                self.messages.append({"role": "user", "content": tool_results})
            else:
                # No more tool calls, we're done
                # Auto-save conversation
                self._auto_save_if_enabled()
                break

    def reset(self) -> None:
        """Clear conversation history and saved state."""
        self.messages = []
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        # Clear saved conversation
        from .conversation_store import clear_conversation
        clear_conversation()

    def compact_history(self, keep_recent: int = 4) -> str:
        """
        Compact conversation history by summarizing older messages.

        Args:
            keep_recent: Number of recent message pairs to keep intact

        Returns:
            Summary of what was compacted
        """
        if len(self.messages) <= keep_recent * 2:
            return "Conversation too short to compact."

        # Split messages into old (to summarize) and recent (to keep)
        split_point = len(self.messages) - (keep_recent * 2)
        old_messages = self.messages[:split_point]
        recent_messages = self.messages[split_point:]

        # Strip orphaned tool_result blocks from the first recent message
        # These would have no matching tool_use after compacting
        if recent_messages and recent_messages[0]["role"] == "user":
            content = recent_messages[0].get("content", [])
            if isinstance(content, list):
                # Filter out tool_result blocks
                filtered_content = [
                    block for block in content
                    if not (isinstance(block, dict) and block.get("type") == "tool_result")
                ]
                if filtered_content:
                    recent_messages[0] = {**recent_messages[0], "content": filtered_content}
                else:
                    # If the message only had tool_results, remove it entirely
                    recent_messages = recent_messages[1:]

        # Build a text representation of old messages for summarization
        conversation_text = ""
        for msg in old_messages:
            role = msg["role"]
            content = msg.get("content", "")

            if isinstance(content, str):
                conversation_text += f"{role.upper()}: {content}\n\n"
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            conversation_text += f"TOOL RESULT: {block.get('content', '')[:200]}...\n\n"
                        elif block.get("type") == "text":
                            conversation_text += f"{role.upper()}: {block.get('text', '')}\n\n"
                    elif hasattr(block, "type"):
                        if block.type == "text":
                            conversation_text += f"{role.upper()}: {block.text}\n\n"
                        elif block.type == "tool_use":
                            conversation_text += f"TOOL CALL: {block.name}({block.input})\n\n"

        # Use Claude to summarize
        summary_response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Summarize this conversation history concisely, preserving key information:
- What decks/cards were discussed
- What cards were added (include the words/terms)
- Any user preferences mentioned
- Current task context

Conversation:
{conversation_text[:15000]}

Provide a brief summary (2-4 paragraphs max):"""
            }]
        )

        summary = summary_response.content[0].text

        # Create new message history with summary + recent messages
        self.messages = [
            {
                "role": "user",
                "content": f"[CONVERSATION SUMMARY]\n{summary}\n[END SUMMARY]\n\nContinuing our conversation..."
            },
            {
                "role": "assistant",
                "content": "I understand. I've noted the context from our previous conversation. How can I help you continue?"
            }
        ] + recent_messages

        # Update token tracking (estimate reduction)
        old_tokens = self.input_tokens_used
        self.input_tokens_used = int(self.input_tokens_used * 0.3)  # Rough estimate
        tokens_saved = old_tokens - self.input_tokens_used

        # Save compacted conversation to disk
        self._auto_save_if_enabled()

        return f"Compacted {len(old_messages)} messages into summary. Estimated tokens saved: ~{tokens_saved:,}"
