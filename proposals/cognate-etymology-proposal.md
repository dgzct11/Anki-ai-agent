# Cognate and Etymology-Powered Spanish Learning Proposal

## Context

The user speaks English, Romanian, and French -- three languages that share massive Latin-derived vocabulary with Spanish. This creates an extraordinary shortcut: potentially 40-60% of CEFR vocabulary at any level is already "half-known" through cognates. This proposal describes how to systematically exploit that advantage within the ankicli-v2 system.

---

## 1. Cognate-Powered Card Creation

### How It Should Work

When the AI assistant creates a card for a Spanish word, it should check whether that word has recognizable cognates in the user's known languages and, if so, include a brief cognate line on the card back.

### Recommended Presentation: A "Cognates" Line on the Card Back

Add a single line after the main word, before examples:

```html
<b>comunicar</b> <i>(to communicate)</i><br>
<i style="color:#888">cf. FR communiquer / RO a comunica / EN communicate -- from Latin communicare</i><br><br>
<b>Examples:</b><br>
1. ...
```

This is minimal, non-intrusive, and triggers the "aha, I already know this" recognition. It should NOT be a separate Anki field or note type -- that would complicate the existing Basic note type that the system already uses. A styled HTML line is the right level of complexity.

### Handling False Cognates

False cognates get a WARNING line instead of a cognate line, in a distinct color:

```html
<b>embarazada</b> <i>(pregnant)</i><br>
<i style="color:#c44">FALSE FRIEND: Not "embarrassed" (= avergonzado/a). From Spanish embarazar (to obstruct/impede).</i><br><br>
```

This is critical -- false cognates need to be flagged MORE prominently than true cognates, because the learner's instinct will be wrong and needs active correction.

### Etymology Depth: Just Enough, Not Too Much

The Latin root should appear only when it genuinely aids memory. Good examples:
- "hablar (to speak) -- from Latin fabulare (to tell stories) -- cf. EN fable" -- this is memorable and useful
- "escribir (to write) -- from Latin scribere -- cf. FR écrire, RO a scrie, EN scribe" -- the family is obvious

Bad example (too much):
- "mesa (table) -- from Latin mensa (table), from Indo-European *men- (to project), via Vulgar Latin *mesa..." -- this is trivia, not learning aid

**Rule of thumb**: Include etymology when it creates a memorable link or explains a non-obvious cognate. Skip it when the cognate is already transparent (restaurante/restaurant needs no Latin root).

### Implementation: Tool Note Preference

This should be controlled by a tool note preference:

```
set_tool_note("general", "Include cognate hints on card backs for French, Romanian, and English cognates. Flag false cognates with warnings. Include brief Latin etymology when it helps make a non-obvious connection memorable.")
```

This keeps it in the AI prompt layer -- no code changes needed. The Claude assistant already follows tool notes when creating cards.

---

## 2. Cognate Categories and Patterns

### Spanish-French Cognates (Largest Overlap)

Spanish and French are both Western Romance languages. They share the highest mutual intelligibility of any Romance pair. Major patterns:

| Spanish Pattern | French Pattern | Examples |
|---|---|---|
| -ción | -tion | nación/nation, comunicación/communication, educación/éducation |
| -dad/-tad | -té | universidad/université, ciudad/cité, libertad/liberté |
| -mente | -ment | exactamente/exactement, normalmente/normalement |
| -oso | -eux | nervioso/nerveux, peligroso/dangereux |
| -ero | -ier/-eur | cocinero/cuisinier, ingeniero/ingénieur |
| -ar (verbs) | -er (verbs) | hablar/parler (different root!), estudiar/étudier, trabajar/travailler |
| -able | -able | probable/probable, responsable/responsable |

Estimated cognate rates by CEFR level:
- A1 (500 words): ~35-40% have French cognates (~175-200 words). Many basic nouns (familia/famille, restaurante/restaurant) and adjectives (importante/important, diferente/différent).
- A2 (800 words): ~40-45% (~320-360). More abstract vocabulary appears.
- B1 (1200 words): ~45-50% (~540-600). Abstract/academic vocabulary is heavily shared.
- B2 (1500 words): ~50-55% (~750-825). The higher the level, the more Latin-derived (thus shared) vocabulary.
- C1/C2: ~55-65%. Specialized and academic vocabulary is overwhelmingly cognate.

### Spanish-Romanian Cognates (Eastern vs Western Romance)

Romanian diverged earlier and absorbed heavy Slavic, Hungarian, and Turkish influence, but the Latin core remains. Patterns:

| Spanish | Romanian | Notes |
|---|---|---|
| familia | familie | Nearly identical |
| universidad | universitate | -dad -> -tate is systematic |
| comunicar | a comunica | Verb infinitives differ (-ar vs -a) |
| importante | important | Adjectives very close |
| persona | persoană | Vowel shifts but recognizable |
| escuela | școală | Both from Latin schola |
| libro | (carte) | DIVERGENCE: Romanian uses Slavic-origin word |
| hablar | (a vorbi) | DIVERGENCE: Romanian uses Slavic-origin word |

Estimated cognate rates:
- A1: ~25-30% (~125-150 words). Basic nouns and adjectives overlap, but many everyday words diverge (Romanian replaced Latin words with Slavic ones for common concepts).
- A2: ~30-35%.
- B1+: ~35-45%. Academic and formal vocabulary converges back to Latin roots.

Key divergence areas where Romanian went non-Latin:
- Family: Romanian "a iubi" (to love) vs Spanish "amar" -- but Romanian also has "amor" for the noun
- Speaking: Romanian "a vorbi" (Slavic) vs Spanish "hablar"
- Reading: Romanian "a citi" (Slavic) vs Spanish "leer" (Latin legere)

### Spanish-English Cognates (Latin/French Borrowings)

English has a massive Romance vocabulary layer from Norman French and Latin scholarly borrowings. But English cognates are often "formal register" equivalents:

| Spanish (everyday) | English Cognate (often formal) | English Everyday |
|---|---|---|
| comunicar | communicate | talk/tell |
| residencia | residence | home/house |
| transportar | transport | carry/move |
| permitir | permit | allow/let |
| elegir | elect | choose/pick |
| obtener | obtain | get |

Estimated cognate rates:
- A1: ~25-30% (~125-150 words). But many are "semi-transparent" -- the learner needs to be told "familia = family" once, then it sticks.
- A2: ~30-35%.
- B1: ~35-40%.
- B2+: ~45-55%. Academic English is essentially Latin, so Spanish cognates are abundant.

### Combining All Three Languages

For this specific user, the combined cognate coverage is remarkable:

- A1: ~55-65% of 500 words are cognate with AT LEAST ONE of {English, French, Romanian}. That is ~275-325 "free" words.
- A2: ~60-70%.
- B1+: ~65-75%.

This means the user can potentially recognize the majority of CEFR vocabulary with minimal effort. The remaining 25-40% (Germanic-origin English words that diverge, uniquely Spanish terms, Arabic-origin words) is where real study effort is needed.

---

## 3. Etymology on Cards: Practical Guidelines

### When Etymology Helps (Include It)

1. **Disambiguating confusing pairs** (highest value):
   - ser vs estar: "ser from Latin sedere (to be seated/settled) = permanent. estar from Latin stare (to stand) = current state/position."
   - por vs para: "por from Latin pro (for/because of) = cause/exchange. para from Latin per ad (toward) = purpose/destination."
   - saber vs conocer: "saber from Latin sapere (to taste/be wise) = factual knowledge. conocer from Latin cognoscere (to become acquainted) = familiarity."

2. **Making non-obvious cognates click**:
   - "hallar (to find) -- from Latin afflare (to breathe upon/sniff out) -- think of a hunting dog finding prey"
   - "hablar (to speak) -- from Latin fabulare (to tell stories) -- cf. English 'fable', French 'fable', Romanian 'fabulă'"
   - "hijo (son) -- from Latin filius -- cf. French fils, Romanian fiu, English filial"

3. **Latin root families** (shows the word is not isolated):
   - "escribir (to write) -- Latin scribere -- cf. describir, inscribir, prescribir, manuscrito, escritor"
   - This shows the learner that learning one root unlocks many words.

### When Etymology is Noise (Skip It)

- Transparent cognates: "restaurante" does not need "from Latin restaurare." The learner already gets it.
- Complex chains: The user does not need Proto-Indo-European reconstructions.
- Disputed etymologies: If linguists debate the origin, do not clutter the card.

### Suggested Format

For cards where etymology adds value, add it as a subtle line:

```html
<b>saber</b> <i>(to know - facts/skills)</i><br>
<i style="color:#888">Latin sapere (to taste/be wise) -- cf. FR savoir, RO a ști (divergent), EN savvy/sapient</i><br>
<i style="color:#888">vs. conocer (Latin cognoscere, to become acquainted -- cf. FR connaître, EN cognition)</i><br><br>
```

### Should Etymology Be Optional?

Yes. This should be a tool note preference that the user can toggle:

```
set_tool_note("general", "Include etymology and cognate hints on cards when helpful for memory.")
```

or

```
set_tool_note("general", "Skip etymology. Keep cards minimal.")
```

The system already supports tool notes, so this needs zero code changes.

---

## 4. Cognate-Driven Learning Strategy

### Should the System Teach Cognates First? YES.

This is the single most impactful recommendation in this proposal. Here is the reasoning:

**Cognitive load theory**: Learning a word that is a cognate with a language you know costs roughly 1/3 the effort of learning a completely new word. The phonological form is partially known, the meaning connection is already there, and retention is dramatically higher on first exposure.

**Practical numbers for this user**:
- A1 has ~500 words. If ~300 are cognates, the user can "learn" those 300 in the time it takes to learn ~100 non-cognate words.
- This means the user could reach functional A1 vocabulary in days rather than weeks.
- At B1 level, this advantage compounds: ~600-700 of 1200 words are cognate. Combined with A1+A2 cognates already learned, the user could have ~2000+ word recognition vocabulary very quickly.

### Proposed Cognate-First Ordering

When the `get_cefr_suggestions` tool returns words to learn next, it should prioritize:

1. **Transparent cognates** first (lowest effort, highest reward): restaurante, universidad, comunicar, importante...
2. **Semi-transparent cognates** (need a small push): escribir (scribe), permiso (permission), peligroso (perilous)...
3. **False cognates** (need active correction, but the learner already has a hook): embarazada, éxito, carpeta...
4. **Non-cognate words** last (highest effort): mesa, silla, perro, gato, hablar...

### Cognate Scan Feature

A new tool -- `scan_cognates` -- would be very valuable. It would:

1. Take the user's current CEFR level gap list (unknown words)
2. Flag which ones are cognates with English, French, or Romanian
3. Present them grouped by transparency:
   - "You probably already recognize these: restaurante, universidad, teléfono, familia, importante, diferente..."
   - "These are close if you look: escribir (scribe), permiso (permission), verdad (verity)..."
   - "Watch out for these false friends: éxito (success, not exit), carpeta (folder, not carpet)..."

This gives the user an immediate confidence boost ("I already know 200 words!") and focuses study time on the hard non-cognate vocabulary.

### Progression Strategy

Phase 1 (Week 1-2): "Harvest the cognates"
- Scan A1+A2 for all cognates. Present them in batches.
- The user creates cards for them rapidly (low effort per card, high volume).
- This builds a foundation of 400-600 words quickly.

Phase 2 (Week 2-4): "Fill the gaps"
- Now focus on the non-cognate A1/A2 vocabulary: the Germanic-origin everyday words, the uniquely Spanish terms.
- These need more repetition and effort.

Phase 3 (Ongoing): "Mixed learning"
- At B1+, continue to flag cognates but mix them naturally with non-cognates.
- The ratio of cognates increases at higher levels (more academic vocabulary), so the advantage keeps paying off.

---

## 5. Disambiguation Through Etymology

This is where etymology delivers the MOST practical value -- not as trivia but as a genuine learning tool. The user's biggest confusions will be:

### ser vs estar

Both translate to "to be" in English, but etymology makes the distinction intuitive:

- **ser** from Latin **sedere** (to sit, to be settled) -> permanent, essential, defining qualities
  - "Soy profesor" (I am a teacher -- settled identity)
  - Think: "seated" = permanent position
  - FR: être (from Latin stare, confusingly!) / RO: a fi (from Latin fieri)

- **estar** from Latin **stare** (to stand, to be in a position) -> temporary state, location, condition
  - "Estoy cansado" (I am tired -- current state)
  - Think: "standing" = current position, changeable
  - EN: "state" and "status" come from the same root

**Card format suggestion:**
```html
<b>ser</b> (to be -- identity/essence)<br>
<i style="color:#888">From Latin sedere (to sit/be settled) -- think "who you ARE at your core"</i><br>
<i style="color:#c44">vs. estar (Latin stare, to stand) = temporary state/location</i><br>
```

### por vs para

- **por** from Latin **pro** (for, because of, in exchange for)
  - Cause, reason, exchange, duration, movement through
  - "Gracias por tu ayuda" (because of), "Lo compré por diez euros" (in exchange for)

- **para** from Latin **per ad** (toward, for the purpose of)
  - Purpose, destination, deadline, recipient
  - "Estudio para aprender" (in order to), "Es para ti" (destined for you)

**Mnemonic**: por = backward-looking (cause/reason), para = forward-looking (purpose/destination)

### saber vs conocer

- **saber** from Latin **sapere** (to taste, to be wise) -> factual knowledge, skills
  - "Sé hablar español" (I know how to speak Spanish)
  - cf. EN "sapient", "savvy", FR "savoir", RO "a ști" (Slavic replacement, but "savant" exists)

- **conocer** from Latin **cognoscere** (to become acquainted with) -> familiarity, personal knowledge
  - "Conozco a María" (I know Maria personally)
  - cf. EN "cognition", "recognize", FR "connaître", RO "a cunoaște"

### preterite vs imperfect

Etymology of the tenses themselves helps:
- **Preterite** (pretérito): from Latin praeteritus (gone by) -- completed, done, over
- **Imperfect** (imperfecto): from Latin imperfectus (not completed) -- ongoing, habitual, unfinished background

This is genuinely useful: "Was the action COMPLETED (preterite) or ONGOING/HABITUAL (imperfect)?"

---

## 6. Cross-Language Word Networks

### Latin Root Families

These are powerful because learning one root unlocks 5-10 Spanish words plus connections to all known languages:

**scribere (to write)**
- Spanish: escribir, describir, inscribir, prescribir, suscribir, manuscrito, escritor, escritura
- French: écrire, décrire, inscrire, prescrire, manuscrit, écrivain
- Romanian: a scrie, a descrie, a înscrie, a prescrie, manuscris, scriitor
- English: scribe, describe, inscribe, prescribe, subscribe, manuscript, scripture

**ducere (to lead)**
- Spanish: conducir, producir, reducir, introducir, educación, conductor, producto
- French: conduire, produire, réduire, introduire, éducation
- Romanian: a conduce, a produce, a reduce, a introduce, educație
- English: conduct, produce, reduce, introduce, educate, duke

**ponere (to place/put)**
- Spanish: poner, componer, deponer, disponer, exponer, imponer, proponer, suponer
- French: poser, composer, déposer, disposer, exposer, imposer, proposer, supposer
- Romanian: a pune, a compune, a depune, a dispune, a expune, a impune, a propune, a presupune
- English: compose, depose, dispose, expose, impose, propose, suppose

**videre (to see)**
- Spanish: ver, revisar, televisión, evidente, providencia, visión
- French: voir, réviser, télévision, évident, providence, vision
- Romanian: a vedea, a revizui, televiziune, evident, providență, viziune
- English: video, revise, television, evident, providence, vision

### Greek Root Families

Important for academic/scientific vocabulary:

**graphein (to write)**: Spanish grafía, caligrafía, fotografía, biografía, geografía / all nearly identical across FR, RO, EN

**logos (word/study)**: Spanish biología, psicología, tecnología, sociología / identical across all four languages

**phone (voice/sound)**: Spanish teléfono, micrófono, fonema / transparent across all languages

### Arabic Contributions (Unique Spanish Heritage)

These are NOT cognates with French, Romanian, or English, so they require extra study effort:

- **al-** prefix words: álgebra, alcohol, alfombra (carpet), almohada (pillow), alcalde (mayor), aldea (village), almanaque (almanac), algodón (cotton)
- Food: aceite (oil, from az-zait), aceituna (olive), azúcar (sugar), naranja (orange -- this one DID spread to other languages)
- Architecture: azulejo (tile), alcoba (bedroom), alhambra
- Geography: guadalquivir (great river), many place names

**Strategic note**: Arabic-origin words should be flagged as "no cognate help available" so the learner knows to invest extra effort in these.

---

## 7. False Friends Database

### Critical False Friends (Spanish-English)

These are the most dangerous because English is the user's strongest second language:

| Spanish | Means | Looks Like | English Actually Means |
|---|---|---|---|
| embarazada | pregnant | embarrassed | avergonzada |
| éxito | success | exit | salida |
| carpeta | folder | carpet | alfombra |
| realizar | to carry out | to realize | darse cuenta |
| actual | current | actual | real, verdadero |
| asistir | to attend | to assist | ayudar |
| constipado | having a cold | constipated | estreñido |
| sensible | sensitive | sensible | sensato |
| soportar | to tolerate | to support | apoyar |
| pretender | to intend/try | to pretend | fingir |
| largo | long | large | grande |
| recordar | to remember | to record | grabar |
| librería | bookshop | library | biblioteca |
| conductor | driver | conductor (music) | director |
| discusión | argument | discussion | conversación |
| suceso | event | success | éxito |
| contestar | to answer | to contest | impugnar |
| delito | crime | delight | deleite |
| disgusto | displeasure | disgust | asco |

### False Friends (Spanish-French)

Fewer but still important:

| Spanish | Means | French | French Means |
|---|---|---|---|
| salir | to leave | salir (to soil) | to make dirty |
| largo | long | large | wide |
| constipado | cold (illness) | constipé | constipated |

### False Friends (Spanish-Romanian)

Fewer still, since both are closer to Latin:

| Spanish | Means | Romanian | Potential Confusion |
|---|---|---|---|
| burro | donkey | bur (navel) | Different word entirely |
| largo | long | larg | larg means "wide" in Romanian |

### Drilling Strategy for False Friends

1. **Tag all false friend cards** with `false_friend` and `false_friend::source_language` (e.g., `false_friend::english`).
2. **Present them in contrastive pairs**: Create the card for "embarazada" immediately alongside "avergonzado" so the correct mapping is reinforced.
3. **Extra review frequency**: The user should see false friend cards more often. Anki's algorithm handles this naturally if the user initially gets them wrong, but we can also suggest a dedicated "False Friends" subdeck for focused practice.
4. **Mnemonic emphasis**: The card back for false friends should include a memorable distinction:
   ```html
   <b>embarazada</b> = pregnant<br>
   <i style="color:#c44">NOT embarrassed! Think: "She's embarrassed because she's pregnant" (mnemonic)</i><br>
   <i>Embarrassed = avergonzado/a</i>
   ```

---

## 8. Implementation Ideas (High Level)

### Changes to CEFR Vocabulary JSON (Optional Enhancement)

Add a `cognates` field to the vocabulary JSON entries:

```json
{
  "word": "comunicar",
  "english": "to communicate",
  "pos": "verb",
  "category": "media_communication",
  "cognates": {
    "fr": "communiquer",
    "ro": "a comunica",
    "en": "communicate",
    "latin": "communicare"
  },
  "cognate_transparency": "transparent"
}
```

And for false friends:

```json
{
  "word": "embarazada",
  "english": "pregnant",
  "pos": "adjective",
  "false_friends": {
    "en": {"word": "embarrassed", "correct": "avergonzado/a"},
    "fr": {"word": "embarrassée", "correct": "avergonzado/a"}
  }
}
```

**However**: This is a LOT of data entry for ~6500 words. A more practical approach is:

### AI-Generated Cognates at Card Creation Time (Recommended)

Since the assistant is Claude, it already KNOWS the cognates. The most practical implementation is:

1. **Tool note preference** (zero code): Set a tool note telling Claude to include cognate hints and etymology when creating cards. Claude already knows Latin, French, Romanian, and can generate accurate cognate information inline.

2. **`cognate_transparency` field in CEFR JSON** (small data effort): Add just a simple field to each vocabulary entry: `"cognate_type": "transparent"`, `"cognate_type": "semi_transparent"`, `"cognate_type": "false_friend"`, or `"cognate_type": "none"`. This requires less data entry than full cognate mappings and enables the cognate-first sorting in suggestions.

3. **Cognate scan tool** (new tool): A `scan_cognates` tool that takes the user's unknown word list and has Claude categorize them into transparent/semi-transparent/false_friend/non-cognate groups. This could be implemented as a delegate operation (similar to `all_cards_delegate`) that processes words in batches.

4. **False friends tag** (trivial): When creating cards for false friends, the assistant adds a `false_friend` tag. This is just a prompt instruction, no code change.

5. **Suggestion reordering** (code change in `cefr.py`): Modify `get_suggestions()` to sort by `cognate_type` if the field exists, putting transparent cognates first and non-cognates last.

### Priority Order for Implementation

1. **Tool note for cognate hints on cards** -- zero code, immediate value, do it today
2. **False friend awareness in card creation** -- zero code, just prompt guidance
3. **`cognate_type` field in CEFR vocabulary JSON** -- data work, enables smart ordering
4. **Modified `get_suggestions()` to prefer cognates** -- small code change, big learning acceleration
5. **`scan_cognates` tool** -- moderate effort, but gives the user a powerful "what do I already know?" view
6. **Full cognate data in JSON** -- large data effort, nice-to-have but not essential since Claude generates cognates on the fly

---

## Summary: What Actually Matters for Learning

From most to least impactful:

1. **Cognate-first learning order** -- this is the biggest accelerator. Harvest the low-hanging fruit first.
2. **Etymology for disambiguation** (ser/estar, por/para, saber/conocer) -- this is where etymology transitions from interesting to essential.
3. **False friend drilling** -- actively preventing fossilized errors is worth dedicated effort.
4. **Cognate hints on card backs** -- reinforces the "this is not a foreign word, you already know a version of it" feeling.
5. **Latin root families** -- compounds vocabulary growth by showing word networks.
6. **Cross-language word networks** -- cool and occasionally useful, but less impactful than the above.

The key insight: for a speaker of English, French, and Romanian learning Spanish, the biggest enemy is not unfamiliarity -- it is the FAILURE TO RECOGNIZE what they already know. The system should surface these connections aggressively at first, then gradually shift focus to genuinely new vocabulary.
