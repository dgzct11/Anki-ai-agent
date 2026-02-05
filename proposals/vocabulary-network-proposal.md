# Vocabulary Network Learning: Research Proposal

## Theoretical Foundation

### How the Mental Lexicon Works

Research in psycholinguistics (Aitchison's "Words in the Mind", Meara's vocabulary acquisition models, Nation's vocabulary framework) consistently shows that the mental lexicon is NOT a dictionary -- it is a network. Words are stored with dense interconnections along multiple dimensions:

- **Paradigmatic** (words that can substitute for each other): comprar/adquirir/obtener
- **Syntagmatic** (words that co-occur): comprar + tienda, precio, barato, caro
- **Morphological** (shared roots): comprar/compra/comprador/comprable
- **Phonological** (sound-alike): comprar/comparar (a source of errors!)
- **Conceptual/Semantic** (shared meaning features): comprar/vender (both involve a transaction, but opposite roles)

Research by Schmitt (2000) and Laufer (1998) shows that **depth of word knowledge** (how many connections a word has) is at least as important as **breadth** (how many words you know). A student who knows 2000 words deeply, with rich connections, will outperform one who "knows" 5000 words shallowly.

### The Network Advantage

Studies show:
1. **Words learned in semantic clusters are retained 40% better** than words learned in isolation (Tinkham, 1993; Waring, 1997) -- but with an important caveat.
2. **Closely related words presented simultaneously cause interference** (the "learning burden" problem). Presenting comprar and vender in the same session actually causes MORE confusion initially. The solution: introduce them at different times, then explicitly practice the contrast.
3. **Elaborative retrieval** (recalling a word along with its connections) strengthens memory far more than simple recall (Craik & Lockhart, 1972, depth of processing theory).
4. **Collocational knowledge is the #1 predictor of fluency** (Pawley & Syder, 1983). Knowing that you say "hacer una pregunta" not "pedir una pregunta" is what separates intermediate from advanced speakers.

---

## 1. How New Words Should Be Added

### 1A. The Connection Discovery Flow

When a user adds "comprar" (to buy), the system should:

**Step 1: Check existing connections (BEFORE adding)**
Scan the user's existing cards for related words. Show what they already know:
```
You already have these related words:
  tienda (A1) - store
  dinero (A1) - money
  precio (A2) - price

comprar connects to these existing words through:
  Theme: Shopping and Establishments
  Grammar: A2 preterite (compré), B1 subjunctive (compre)
```

This does three things: avoids duplicates, activates existing knowledge, and shows the learner their growing network.

**Step 2: Suggest connections (AFTER adding)**
After the card is created, suggest 3-5 related words the user does NOT yet have, prioritized by:
1. **CEFR level proximity** (suggest words at their current level first)
2. **Frequency** (more common words first)
3. **Connection strength** (direct antonyms/synonyms before loose thematic associations)

```
Related words you could add next:
  vender (A2) - to sell [antonym]
  la compra (A2) - the purchase [morphological]
  el/la comprador/a (B1) - the buyer [morphological]
  regatear (B2) - to haggle [thematic]
  adquirir (C1) - to acquire [synonym, formal register]
```

**Step 3: Tag with relationship metadata**
Extend the existing `word::comprar` tag system to include relationship tags:
- `word::comprar` (existing)
- `theme::shopping` (thematic cluster)
- `pos::verb` (part of speech)
- `family::compr-` (morphological family root)
- `level::A2` (CEFR level)

This enables the system to query relationships programmatically.

### 1B. Connection Depth: How Many Layers?

Proposed priority layers (system generates these, Claude uses its knowledge):

| Priority | Relation Type | Example for "comprar" | When to Suggest |
|----------|--------------|----------------------|-----------------|
| 1 | Direct antonym | vender | Same session or next |
| 2 | Core collocations | ir de compras, de compraventa | When adding the word |
| 3 | Morphological family | compra, comprador, comprable | At same or next CEFR level |
| 4 | Thematic neighbors | tienda, precio, caro, barato | When building that theme |
| 5 | Synonyms (register) | adquirir, obtener | At higher CEFR level |
| 6 | False friends | comparar (to compare) | When the learner encounters confusion |

Do NOT suggest all at once. The system should drip-feed connections over time, creating an "aha!" moment when the learner sees how comprar, compra, comprador, and compraventa all share the same root.

### 1C. Word Family Groupings

The system should maintain a lightweight graph (not a full graph database -- a JSON structure is sufficient for our scale):

```json
{
  "comprar": {
    "level": "A2",
    "pos": "verb",
    "theme": "shopping",
    "family_root": "compr-",
    "connections": {
      "antonym": ["vender"],
      "morphological": ["compra", "comprador", "comprable", "compraventa"],
      "collocation": ["ir de compras", "comprar a plazos", "poder adquisitivo"],
      "thematic": ["tienda", "precio", "caro", "barato", "dinero", "pagar"],
      "synonym": ["adquirir", "obtener", "conseguir"],
      "confusable": ["comparar"]
    }
  }
}
```

This graph grows as the user adds words. Claude generates the connections when adding each word (it has this knowledge natively), and they are persisted in a `word_network.json` file.

---

## 2. How Connections Should Be Used During Review

### 2A. Connection-Enriched Practice Sentences

When the user reviews "comprar", the practice sentences should INCLUDE words they already know:

Current approach (isolated):
```
Ayer compré un libro.
```

Network-aware approach:
```
Ayer fui a la tienda y compré un libro que costaba diez euros.
     ^already know^      ^reviewing^       ^already know^
```

The system should:
- Pull the user's known words from the word network
- Ask Claude to generate practice sentences that incorporate 2-3 known related words
- Bold or highlight the connections: "Fui a la **tienda** y **compré** un libro por buen **precio**."

This leverages the **elaborative retrieval** principle: each review activates multiple memory nodes simultaneously.

### 2B. Pair-Based Review

Certain word pairs should be practiced TOGETHER once both are learned:

**Antonym pairs**: comprar/vender, ir/venir, subir/bajar, abrir/cerrar
**Semantic contrast pairs**: ser/estar, saber/conocer, por/para (see section 3)
**Verb direction pairs**: llevar/traer, ir/venir, pedir/preguntar

Review format for pairs:
```
Fill in both blanks:
"Ella quiere ___ (buy) el coche, pero él prefiere ___ (sell) lo."
Expected: comprar, vender
```

This tests both words in a single context, forcing the learner to activate the contrast.

### 2C. Connection Map During Review (Optional/On-Demand)

After reviewing a word, optionally show a mini "word map":

```
                adquirir (C1)
                    |
    comprador -- comprar -- vender
        |           |          |
    compra     ir de compras   venta
                    |
              tienda, precio
```

This should NOT be shown every time (it would slow down review). Proposed triggers:
- When the user gets a card wrong (shows connections to help them remember)
- When the user explicitly asks "What's related to this?"
- As a "word exploration" mode separate from review

### 2D. Spaced Activation of Network

When a word comes up for review, the system should also (invisibly) note which connected words were recently reviewed. If "comprar" is reviewed today, "vender" should ideally come up within the next 2-3 sessions. This is "network-aware scheduling" -- not a replacement for Anki's SRS algorithm, but a suggestion layer on top.

Implementation: When the system generates a study session or the user asks "what should I review?", weight connected words of recently-reviewed words slightly higher.

---

## 3. Disambiguation: One English Term, Multiple Spanish Translations

This is the most pedagogically critical section. The one-to-many mapping problem causes more fossilization (permanent errors) than any other vocabulary issue.

### 3A. The Problem, Precisely Defined

Key disambiguation pairs in Spanish:

| English | Spanish Options | CEFR Level |
|---------|----------------|------------|
| to be | ser / estar | A1 |
| to know | saber / conocer | A2 |
| for | por / para | A2 |
| to take | tomar / llevar / coger / sacar | A2-B1 |
| to ask | preguntar / pedir | A2 |
| to play | jugar / tocar | A1-A2 |
| to become | ponerse / volverse / hacerse / convertirse / quedarse | B1-B2 |
| to leave | salir / irse / dejar | A2-B1 |
| to return | volver / devolver / regresar | A2 |
| time | tiempo / vez / hora | A1-A2 |
| to miss | extrañar / perder / faltar | A2-B1 |
| to realize | darse cuenta / realizar | B1 (false friend!) |

### 3B. Special "Disambiguation Cards"

Create a specific card type for these pairs. Instead of one-to-one flashcards, create a "contrast card":

**Front:**
```
WHICH ONE? "to know"
Choose ser/estar | saber/conocer | por/para

1. "Do you know Maria?" -> ___
2. "I know the answer." -> ___
3. "I know how to swim." -> ___
```

**Back:**
```
1. ¿Conoces a María? [conocer = people, places, familiarity]
2. Sé la respuesta. [saber = facts, information]
3. Sé nadar. [saber + infinitive = know how to]

RULE: saber = information/facts/skills
      conocer = people/places/familiarity
```

These cards should be:
- Generated automatically when both words in a disambiguation pair exist in the user's deck
- Tagged with `disambiguation::saber-conocer` for easy querying
- Reviewed MORE frequently than normal cards (they represent high-error-risk items)

### 3C. Contextual Testing (Not Mere Memorization)

The danger with disambiguation is that learners memorize rules ("ser = permanent, estar = temporary") but fail in real usage because the rules are oversimplified.

Better approach -- **context-first testing**:

```
Choose ser or estar:

1. La fiesta ___ en mi casa. (The party is at my house.)
   -> está [location, even though a party isn't "temporary"]

2. Ella ___ muy guapa hoy. (She looks very pretty today.)
   -> está [change from usual, even though being pretty isn't "temporary"]

3. La sopa ___ fría. (The soup is cold.)
   -> está [condition/state, even though cold is a "characteristic" of the soup right now]
```

The system should:
1. Start with clear-cut cases (ser for nationality, estar for location)
2. Progress to ambiguous/tricky cases (ser/estar + adjectives that change meaning)
3. Track which specific contexts cause errors, and increase practice on THOSE

### 3D. Progressive Disambiguation

Do NOT present both words simultaneously when first learning. The progression should be:

1. **Learn word A** (e.g., ser) in isolation with its core uses
2. **Learn word B** (e.g., estar) in isolation with its core uses
3. **Introduce the contrast** only AFTER both are somewhat stable (perhaps 2-3 successful reviews each)
4. **Practice disambiguation** with increasing difficulty
5. **Maintain regular contrast practice** permanently (these pairs never fully "graduate")

### 3E. Error Pattern Tracking

For each disambiguation pair, track:
- Which direction is confused (user uses ser when estar is needed, or vice versa?)
- Which specific contexts cause errors
- Improvement over time

This feeds back into the learning summary:
```
Disambiguation Progress:
  ser/estar: 78% accuracy (struggle with: adjectives that change meaning)
  saber/conocer: 92% accuracy
  por/para: 65% accuracy (struggle with: duration vs deadline)
```

---

## 4. Other Ways Word Networks Improve Learning

### 4A. Collocation Learning

Collocations are the single biggest differentiator between intermediate and advanced speakers. The system should:

**Track and teach collocations explicitly:**
- hacer una pregunta (NOT pedir una pregunta)
- tomar una decisión (NOT hacer una decisión)
- dar un paseo (NOT hacer un paseo)
- echar de menos (NOT perder / extrañar in some regions)

**Implementation:** When adding a verb, Claude should identify its 3-5 most important collocations and include them on the card back. The network should store these:
```json
"hacer": {
  "collocations": [
    {"phrase": "hacer una pregunta", "en": "to ask a question", "note": "NOT pedir"},
    {"phrase": "hacer caso", "en": "to pay attention"},
    {"phrase": "hacer falta", "en": "to be needed/necessary"},
    {"phrase": "hacer cola", "en": "to queue/stand in line"}
  ]
}
```

### 4B. False Friend Alerts

When the user adds a word that has a common English false friend, flag it:

```
WARNING: "realizar" does NOT mean "to realize" (= darse cuenta).
"Realizar" means "to carry out / accomplish."

Common false friends in your collection:
  actualmente ≠ actually (= en realidad)
  embarazada ≠ embarrassed (= avergonzada)
  éxito ≠ exit (= salida)
```

The system should maintain a false-friends list and cross-reference when adding words.

### 4C. Morphological Family Expansion

Spanish morphology is highly regular. Teaching word families multiplies vocabulary:

From "comprar" (A2):
- la compra (purchase) - noun
- el/la comprador/a (buyer) - agent noun
- comprable (purchasable) - adjective
- la compraventa (buying and selling) - compound
- las compras (shopping) - plural noun in set expression

Key morphological patterns to teach:
- -ción/-sión (verb -> noun: comunicar -> comunicación)
- -mente (adjective -> adverb: rápido -> rápidamente)
- -dor/-dora (verb -> agent: trabajar -> trabajador)
- -able/-ible (verb -> adjective: comer -> comestible)
- des-/in- (negation: hacer -> deshacer, posible -> imposible)
- re- (repetition: hacer -> rehacer)

**Suggestion:** When the user reaches B1, start systematically introducing morphological patterns. "You know trabajar. Did you know that -dor makes the person who does it? trabajador = worker. This works for many verbs: comprar -> comprador, vender -> vendedor."

### 4D. Frequency-Based Prioritization of Connected Words

Not all connections are equally valuable. When suggesting related words, prioritize by:

1. **Corpus frequency** (use the 5000 most frequent Spanish words as a baseline)
2. **CEFR level match** (don't suggest C1 words to an A2 learner)
3. **Productive value** (words that unlock many collocations/contexts)
4. **Current learning gap** (words the learner needs for their active theme)

Example: For an A2 learner who added "comprar":
- Suggest "vender" (frequent, same level, core antonym) -- HIGH priority
- Don't suggest "adquirir" (C1, rare in conversation) -- LOW priority
- Suggest "precio" (frequent, same theme, enables "comprar a buen precio") -- HIGH priority

### 4E. Semantic Field Mapping to Themes

Integrate the existing 20 Plan Curricular themes with the word network. When a user is working on "Food and Nutrition," the system can show:

```
Your Food & Nutrition Network:
  KNOW: comer, beber, cocinar, pan, agua, leche (6 words)
  MISSING at your level (A2): arroz, carne, fruta, verdura,
    plato, cuchillo, tenedor, pedir (la cuenta), propina
  CONNECTIONS: comer -> comida, cocinar -> cocina, beber -> bebida
```

This turns abstract CEFR percentages into concrete, actionable word lists organized by the themes the user cares about.

### 4F. Word-of-the-Day from Network Gaps

Each day, suggest a word that:
1. Fills a gap in the user's network (a missing connection from a known word)
2. Is at the appropriate CEFR level
3. Has high frequency/utility

"You know comprar and tienda. Today's word: el/la dependiente (shop assistant) -- connects your shopping network. This word appears in A2 vocabulary."

---

## 5. Implementation Architecture (High Level)

**Data structures needed:**

1. **word_network.json** -- The core graph, keyed by Spanish word:
   ```json
   {
     "meta": {"version": "1.0", "total_words": 247},
     "words": {
       "comprar": {
         "level": "A2", "pos": "verb", "theme": "shopping",
         "family_root": "compr-",
         "in_deck": true, "note_id": 12345,
         "connections": { "antonym": [...], "morphological": [...], ... },
         "collocations": [...],
         "disambiguation_group": null
       }
     },
     "disambiguation_pairs": {
       "ser-estar": { "words": ["ser", "estar"], "category": "to_be", ... },
       "saber-conocer": { "words": ["saber", "conocer"], "category": "to_know", ... }
     }
   }
   ```

2. **disambiguation_tracker.json** -- Error tracking for confusion pairs
3. Integration with existing **learning_summary.json** levels

**Claude tools needed:**
- `get_word_connections(word)` -- Retrieve network data for a word
- `suggest_related_words(word, limit)` -- Get suggestions for what to learn next
- `get_disambiguation_practice(pair)` -- Generate contrast exercises
- `update_word_network(word, connections)` -- Add/update connections when cards are added

**Key principle: Claude generates the connections, the system stores them.**

We do NOT need to pre-build a complete Spanish word graph. When the user adds "comprar," Claude knows its antonyms, collocations, morphological family, etc. The system just asks Claude to provide this information and stores it. The graph grows organically with the user's vocabulary.

---

## 6. Prioritized Recommendations

**Phase 1 (Immediate value, low complexity):**
- Connection suggestions when adding words ("Related words you could add...")
- Tag enrichment (theme, pos, family tags on cards)
- False friend warnings
- Collocation inclusion on card backs

**Phase 2 (High value, medium complexity):**
- Disambiguation cards for the top 15 confusion pairs
- word_network.json graph storage
- Network-aware practice sentences during review
- "What's related?" query capability

**Phase 3 (Advanced, higher complexity):**
- Morphological family expansion suggestions
- Error pattern tracking for disambiguation
- Semantic field progress visualization
- Word-of-the-day from network gaps
- Pair-based review mode
- Connection maps visualization
