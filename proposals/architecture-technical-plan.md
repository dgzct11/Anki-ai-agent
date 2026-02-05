# Core Developer Architecture Assessment and Technical Plan

## 1. Architecture Assessment

### Well-Structured:
- Clean separation of concerns across files
- Generator-based streaming in assistant.chat()
- Dataclass models throughout
- Click CLI with clean command structure
- Rich for terminal rendering

### Needs Refactoring:
1. **assistant.py is a God Object** (1,142 lines) - 400-line if/elif chain for tool execution
2. **Tool definitions disconnected from execution** - tools.py schemas and assistant.py handlers are separate
3. **System prompt hardcoded and Spanish-specific** - embedded in assistant.py
4. **Duplicate delegate handlers** - ~80% identical code
5. **Storage paths scattered** - 4 files defining same directory independently
6. **No typing for learning_summary data** - raw dicts everywhere
7. **Minimal test coverage** - only test_models.py

---

## 2. Tool Notes System (~125 lines)

- Add `tool_notes: dict[str, str]` to Config
- Dynamic system prompt injection via `_build_tool_notes_section()`
- CLI: `ankicli notes list/set/remove/clear`
- Chat: `notes` command

---

## 3. Translation Practice (~365 lines)

- New `translation_practice.py` with PracticeSession, PracticeResult
- Due card fetching via AnkiConnect `is:due` queries
- Claude evaluation via focused single API call (Haiku for cost)
- Chat sub-loop with practice mode
- New tool: `start_translation_practice`

---

## 4. Grammar Quizzes (~450 lines)

- New `grammar_quiz.py` with QuizQuestion, QuizSession, QuizResult
- 5 question types: fill-blank, multiple choice, conjugation, error correction, transformation
- Claude generates questions based on CEFR level + known vocabulary
- New tool: `start_grammar_quiz`

---

## 5. Enhanced Progress Tracking (~320 lines)

- New `progress.py` with SessionRecord, PracticeScore, QuizScore, ProgressData
- Consolidates learning_summary + new tracking
- Streaks, practice accuracy trends, weak word tracking

---

## 6. Technical Debt Fixes

### Priority 1: Extract Tool Handlers
Decorator-based handler registry -> eliminates 400-line if/elif chain.

### Priority 2: Centralize Storage Paths
Single `paths.py` module.

### Priority 3: Deduplicate Delegate Handlers
Merge into single method with `cards` parameter.

### Priority 4: Extract System Prompt
Composable sections, language-specific formatting separate from behavior.

### Priority 5: Type the Learning Summary
Proper dataclasses instead of raw dicts.

---

## 7. Proposed File Structure

```
src/ankicli/
    data/
        cefr_spanish.json        # CEFR vocabulary/grammar lists
    paths.py                     # Centralized storage paths
    tool_handlers.py             # Tool execution handlers
    translation_practice.py      # Translation practice mode
    grammar_quiz.py              # Grammar quiz generation
    progress.py                  # Enhanced progress tracking
    cefr.py                      # CEFR data loading and matching
```

### Estimated Total: ~1,960 lines of new/modified code

### Implementation Order:
1. paths.py + refactor storage paths
2. tool_handlers.py extraction
3. CEFR data generation + cefr.py module
4. Tool notes system
5. CEFR-aware progress tracking
6. Translation practice
7. Grammar quizzes
