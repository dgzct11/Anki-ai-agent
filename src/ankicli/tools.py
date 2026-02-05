"""Tool definitions for Claude API."""

ANKI_TOOLS = [
    {
        "name": "list_decks",
        "description": "List all Anki decks with their card counts (new, learning, review)",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_note_types",
        "description": "List available note types (card templates) in Anki",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "add_card",
        "description": "Add a new flashcard to a deck. Use HTML formatting (<b>bold</b>, <i>italic</i>, <br> for line breaks). For Spanish vocab: front=English definition, back=Spanish word (bold) + conjugations (for verbs) + 5 example sentences. IMPORTANT: Always include a 'word::spanish_word' tag for quick lookup (verbs in infinitive, nouns without articles, lowercase). Example: word::hablar, word::casa, word::rápido.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck to add the card to"
                },
                "front": {
                    "type": "string",
                    "description": "Front side - English definition/meaning (plain text usually)"
                },
                "back": {
                    "type": "string",
                    "description": "Back side with HTML formatting: <b>Spanish word</b>, conjugations, and 5 examples. Use <br> for line breaks, <b> for headers, <i> for notes/tense labels."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "MUST include 'word::spanish_word' tag (infinitive for verbs, no article for nouns, lowercase). Also include type tags: 'verb', 'noun', 'adjective', 'irregular', etc."
                },
                "note_type": {
                    "type": "string",
                    "description": "Note type to use (default: 'Basic')"
                }
            },
            "required": ["deck_name", "front", "back"]
        }
    },
    {
        "name": "add_multiple_cards",
        "description": "Add multiple flashcards to a deck at once. Use HTML formatting (<b>, <i>, <br>). For bulk card creation (10, 20, 50+ cards). Spanish vocab: front=English, back=HTML-formatted Spanish + conjugations + 5 examples. IMPORTANT: Always include a 'word::spanish_word' tag for quick lookup (verbs in infinitive, nouns without articles, lowercase).",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck to add cards to"
                },
                "cards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "front": {"type": "string", "description": "English definition/meaning (plain text)"},
                            "back": {"type": "string", "description": "HTML-formatted: <b>Spanish word</b>, conjugations, 5 examples. Use <br> for breaks, <b>/<i> for formatting."},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "MUST include 'word::spanish_word' tag (infinitive for verbs, no article for nouns, lowercase). Also: 'verb', 'noun', 'adjective', 'irregular', etc."
                            }
                        },
                        "required": ["front", "back"]
                    },
                    "description": "List of cards to add. Can include many cards (10, 20, 50+) in a single call."
                },
                "note_type": {
                    "type": "string",
                    "description": "Note type to use for all cards (default: 'Basic')"
                }
            },
            "required": ["deck_name", "cards"]
        }
    },
    {
        "name": "search_cards",
        "description": "Search for existing cards in Anki using search syntax. Returns note IDs that can be used for editing/deleting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query using Anki syntax (e.g., 'deck:MyDeck', 'tag:vocab', 'front:*word*', '*' for all)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_deck_cards",
        "description": "Get all cards in a specific deck",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of cards to return (default: 50)"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "get_note",
        "description": "Get a single note/card by its ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "The note ID"
                }
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "update_card",
        "description": "Update an existing card's front, back, or tags. Use HTML formatting for content (<b>, <i>, <br>). When updating tags, always preserve the 'word::spanish_word' tag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "The note ID to update"
                },
                "front": {
                    "type": "string",
                    "description": "New front content with HTML formatting (omit to keep existing)"
                },
                "back": {
                    "type": "string",
                    "description": "New back content with HTML formatting (omit to keep existing)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New tags (replaces all existing). Always preserve 'word::spanish_word' tag."
                }
            },
            "required": ["note_id"]
        }
    },
    {
        "name": "update_multiple_cards",
        "description": "Update multiple cards at once. Use HTML formatting for content (<b>, <i>, <br>). When updating tags, always preserve the 'word::spanish_word' tag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "note_id": {"type": "integer", "description": "The note ID to update"},
                            "front": {"type": "string", "description": "New front content (HTML formatted)"},
                            "back": {"type": "string", "description": "New back content (HTML formatted)"},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "New tags"
                            }
                        },
                        "required": ["note_id"]
                    },
                    "description": "List of updates to apply"
                }
            },
            "required": ["updates"]
        }
    },
    {
        "name": "delete_cards",
        "description": "Delete one or more cards by their note IDs",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of note IDs to delete"
                }
            },
            "required": ["note_ids"]
        }
    },
    {
        "name": "add_tags_to_cards",
        "description": "Add tags to multiple cards",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of note IDs to add tags to"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to add"
                }
            },
            "required": ["note_ids", "tags"]
        }
    },
    {
        "name": "remove_tags_from_cards",
        "description": "Remove tags from multiple cards",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of note IDs to remove tags from"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to remove"
                }
            },
            "required": ["note_ids", "tags"]
        }
    },
    {
        "name": "move_cards_to_deck",
        "description": "Move cards to a different deck",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of note IDs to move"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Target deck name"
                }
            },
            "required": ["note_ids", "deck_name"]
        }
    },
    {
        "name": "create_deck",
        "description": "Create a new deck",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the new deck (use :: for subdecks, e.g., 'Parent::Child')"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "sync_anki",
        "description": "Sync Anki with AnkiWeb to upload/download changes",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_deck_stats",
        "description": "Get statistics for a specific deck: total cards, new, learning, and review counts",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "get_deck_summary",
        "description": "Get a comprehensive summary of a deck including stats, tags used, and sample cards",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum cards to analyze (default: 100)"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "list_deck_fronts",
        "description": "List just the front (question/English) side of all cards in a deck - useful for seeing what words/concepts are already covered",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum cards to return (default: 200)"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "get_collection_stats",
        "description": "Get overall statistics for the entire Anki collection: total decks, total cards, cards due across all decks",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_word_exists",
        "description": "Check if a word or phrase already exists in a deck. Use this BEFORE adding new cards to avoid duplicates. Returns matching cards if found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "The word or phrase to search for"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Optional: limit search to a specific deck"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "check_words_exist",
        "description": "Check if multiple words already exist in a deck. Use this before bulk adding to filter out duplicates. Returns which words were found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of words to check"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Optional: limit search to a specific deck"
                }
            },
            "required": ["words"]
        }
    },
    {
        "name": "find_card_by_word",
        "description": "Find a card by its Spanish word tag. Uses the 'word::spanish_word' tag format. Fast and exact matching - preferred way to check if a word already exists before adding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to find (infinitive for verbs, no article for nouns, lowercase). Example: 'hablar', 'casa', 'rápido'"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Optional: limit search to a specific deck"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "find_cards_by_words",
        "description": "Find multiple cards by their Spanish word tags. Uses the 'word::spanish_word' tag format. Returns which words exist and which don't. Use before bulk adding to filter duplicates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spanish words to check (infinitive for verbs, no article for nouns, lowercase)"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Optional: limit search to a specific deck"
                }
            },
            "required": ["words"]
        }
    },
    {
        "name": "compact_conversation",
        "description": "Compact the conversation history by summarizing older messages. Use this when context is getting full (>50%) to free up space while preserving important information. This is automatic maintenance - call it proactively when needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for compacting (e.g., 'context at 60%', 'long conversation')"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_learning_summary",
        "description": "Get the persistent Spanish learning progress summary. Shows for each CEFR level (A1-B2): what you already know, what you need to learn to complete that level, and estimated coverage percentage.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_learning_summary",
        "description": "IMPORTANT: Call this AFTER adding cards to update the persistent learning summary. Updates what you know and what you need to learn for each level. This persists across sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2"],
                    "description": "CEFR level being updated"
                },
                "words_added": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spanish words/phrases just added to this level"
                },
                "what_i_know_summary": {
                    "type": "string",
                    "description": "Detailed text summary of what the user has mastered at this level. Be specific about vocabulary areas, grammar concepts, and practical skills. Example: 'Strong foundation in daily routine verbs (despertarse, ducharse, etc), emotion adjectives, common adverbs. Can describe past events using preterite tense.'"
                },
                "grammar_concepts_learned": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grammar concepts the user has learned (e.g., 'Present tense', 'Preterite tense', 'Reflexive verbs')"
                },
                "topics_covered": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topic areas covered (e.g., 'Daily routines', 'Restaurant', 'Travel', 'Health')"
                },
                "what_to_learn_summary": {
                    "type": "string",
                    "description": "Detailed text summary of what's still needed to complete this level. Be specific about gaps."
                },
                "vocabulary_gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Vocabulary categories still needed (e.g., 'weather', 'clothing', 'household-items')"
                },
                "grammar_gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grammar concepts still needed (e.g., 'Imperfect tense', 'Object pronouns')"
                },
                "priority_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested priority topics to focus on next"
                },
                "estimated_coverage": {
                    "type": "integer",
                    "description": "Estimated % coverage of this level (0-100)"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes about overall progress"
                }
            },
            "required": ["level", "words_added"]
        }
    },
    {
        "name": "set_tool_note",
        "description": "Save a user preference/note that modifies how a tool behaves. Use 'general' as tool_name for preferences that apply to all card creation (e.g., 'use informal Spanish', 'include 3 examples instead of 5'). Use specific tool names like 'add_card' or 'add_multiple_cards' for tool-specific preferences. Proactively offer to save preferences when the user expresses a preference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name to attach the note to, or 'general' for global preferences. Examples: 'general', 'add_card', 'add_multiple_cards'"
                },
                "note": {
                    "type": "string",
                    "description": "The preference/instruction to save. Be specific and actionable. Example: 'Use Latin American Spanish. Include 3 example sentences instead of 5. Use informal tu form.'"
                }
            },
            "required": ["tool_name", "note"]
        }
    },
    {
        "name": "get_tool_notes",
        "description": "List all saved user preferences/tool notes. Shows what preferences are currently active.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "remove_tool_note",
        "description": "Remove a saved user preference/tool note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name whose note to remove, or 'general'"
                }
            },
            "required": ["tool_name"]
        }
    },
    {
        "name": "start_grammar_quiz",
        "description": "Start an interactive grammar quiz session. Claude generates questions dynamically based on the topic and CEFR level. The quiz runs in the chat with Rich-formatted panels for each question. After the quiz, offers to create Anki cards for weak areas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Grammar topic to quiz on (e.g., 'Preterite tense - regular verbs', 'Ser vs Estar'). Use get_learning_summary to see grammar gaps."
                },
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2"],
                    "description": "CEFR level for question difficulty"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of questions (default: 5, max: 50). Overridden by 'size' if set."
                },
                "size": {
                    "type": "string",
                    "enum": ["quick", "assessment", "comprehensive"],
                    "description": "Quiz size preset: 'quick' (10q, 1 topic), 'assessment' (25-30q, full CEFR level), 'comprehensive' (50q, multi-level). Overrides count."
                },
                "question_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["fill_in_blank", "multiple_choice", "conjugation", "error_correction", "sentence_transformation"]
                    },
                    "description": "Question types to include (default: all types)"
                }
            },
            "required": ["topic", "level"]
        }
    },
    {
        "name": "log_quiz_results",
        "description": "Log the results of a completed grammar quiz session. Updates mastery tracking for the grammar topic. Called automatically after a quiz, but can also be called manually.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Grammar topic that was quizzed"
                },
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2"],
                    "description": "CEFR level of the quiz"
                },
                "questions_attempted": {
                    "type": "integer",
                    "description": "Number of questions attempted"
                },
                "correct": {
                    "type": "integer",
                    "description": "Number of correct answers"
                },
                "weak_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grammar areas the user struggled with"
                }
            },
            "required": ["topic", "level", "questions_attempted", "correct"]
        }
    },
    {
        "name": "all_cards_delegate",
        "description": "Process ALL cards in a deck using parallel sub-agents. Each card is sent to a Claude sub-agent with your prompt. Use for bulk operations like formatting, adding examples, fixing content. Shows progress bar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the deck to process"
                },
                "prompt": {
                    "type": "string",
                    "description": "Instructions for transforming each card. Sub-agent sees front, back, and tags."
                },
                "workers": {
                    "type": "integer",
                    "description": "Parallel workers (default: 5, max: 10)"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without applying (default: false)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max cards to process (default: all)"
                }
            },
            "required": ["deck_name", "prompt"]
        }
    },
    {
        "name": "card_subset_delegate",
        "description": "Process specific cards (by note IDs) using parallel sub-agents. Use after search_cards to process matching results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Note IDs to process (from search_cards)"
                },
                "prompt": {
                    "type": "string",
                    "description": "Instructions for transforming each card"
                },
                "workers": {
                    "type": "integer",
                    "description": "Parallel workers (default: 5, max: 10)"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without applying (default: false)"
                }
            },
            "required": ["note_ids", "prompt"]
        }
    },
    {
        "name": "start_translation_practice",
        "description": "Start a translation practice session using cards from an Anki deck. Claude presents phrases in one language and the user translates to the other. Evaluates meaning, grammar, naturalness, and vocabulary. Can also mark due cards as reviewed in Anki (with user confirmation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Name of the Anki deck to practice from"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of questions in the session (default: 10)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["en_to_es", "es_to_en"],
                    "description": "Translation direction (default: en_to_es)"
                },
                "card_source": {
                    "type": "string",
                    "enum": ["due", "new", "mixed", "all"],
                    "description": "Which cards to use: 'due' for review cards, 'new' for unseen, 'mixed' for both, 'all' for any (default: mixed)"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "log_practice_session",
        "description": "Log a completed practice session to the learning summary for long-term tracking. Call this after a practice session ends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "practice_type": {
                    "type": "string",
                    "enum": ["translation", "grammar_quiz"],
                    "description": "Type of practice session"
                },
                "direction": {
                    "type": "string",
                    "description": "Translation direction used (en_to_es or es_to_en)"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Deck practiced from"
                },
                "phrases_attempted": {
                    "type": "integer",
                    "description": "Total phrases attempted"
                },
                "correct": {
                    "type": "integer",
                    "description": "Number correct"
                },
                "partial": {
                    "type": "integer",
                    "description": "Number partially correct"
                },
                "incorrect": {
                    "type": "integer",
                    "description": "Number incorrect"
                },
                "score_percent": {
                    "type": "number",
                    "description": "Overall score percentage"
                },
                "weak_words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Words the user struggled with"
                },
                "common_errors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Common error patterns observed (e.g., 'gender agreement', 'ser vs estar')"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topics covered in this session"
                }
            },
            "required": ["practice_type", "phrases_attempted", "correct"]
        }
    },
    {
        "name": "get_cefr_progress",
        "description": "Get concrete CEFR vocabulary progress showing exactly how many words you know at each level (e.g., '142/500 A1 words'). Matches your Anki cards against official CEFR word lists. Shows per-category breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                    "description": "Specific CEFR level to show (omit for all levels)"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by theme category (e.g., 'food_nutrition', 'travel_transport')"
                },
                "show_unknown": {
                    "type": "boolean",
                    "description": "Include list of unknown words (default: false)"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Deck to scan (omit to scan all decks)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_cefr_suggestions",
        "description": "Get personalized suggestions for what words to learn next based on CEFR gaps. Prioritizes lowest incomplete level and weakest categories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                    "description": "Specific level to get suggestions for (omit to auto-detect)"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of suggestions (default: 10)"
                },
                "deck_name": {
                    "type": "string",
                    "description": "Deck to check against (omit for all decks)"
                }
            },
            "required": []
        }
    },
    {
        "name": "sync_cefr_progress",
        "description": "Full rescan of Anki cards against CEFR word lists. Updates the cached progress data. Use after bulk card changes or when progress seems stale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Deck to scan (omit to scan all decks)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_error_patterns",
        "description": "Get the user's recurring error patterns from the error journal. Shows which mistakes they make most often (gender agreement, ser vs estar, accent marks, etc.). Use this to tailor practice sessions and provide targeted feedback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_count": {
                    "type": "integer",
                    "description": "Minimum occurrences to include (default: 1)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entries to return (default: 20)"
                }
            },
            "required": []
        }
    },
    {
        "name": "log_error",
        "description": "Log a mistake the user made during practice or quiz. Call this when you notice a recurring error pattern (gender agreement, verb conjugation, ser vs estar, accent marks, etc.). This builds a persistent error journal so you can track improvement over time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "Category of error. Use consistent snake_case labels: gender_agreement, ser_vs_estar, accent_missing, verb_conjugation, word_order, preposition_choice, article_usage, subjunctive_needed, preterite_vs_imperfect, false_friend, spelling, etc."
                },
                "example": {
                    "type": "string",
                    "description": "The user's incorrect text"
                },
                "correction": {
                    "type": "string",
                    "description": "The correct version"
                },
                "context": {
                    "type": "string",
                    "description": "Where the error occurred (e.g., 'translation_practice', 'grammar_quiz', 'conversation')"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags like CEFR level or grammar category (e.g., ['grammar', 'A2'])"
                }
            },
            "required": ["error_type", "example"]
        }
    },
    {
        "name": "get_daily_challenge",
        "description": "Get the daily challenge (word of the day). Picks a new word from CEFR gap areas, presents it with examples, and offers a quick translation exercise. Only generates one challenge per day unless force=true. Call this at the start of each session.",
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Generate a new challenge even if today's was already presented (default: false)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_study_suggestion",
        "description": "Get a personalized study suggestion based on deck stats, CEFR progress, error patterns, and recent quiz results. Use this on session start or when the user asks what to study. Analyzes cards due, weakest CEFR areas, recurring errors, and quiz performance to recommend the most impactful activity.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_related_words",
        "description": "Find semantically related words in CEFR lists for a given Spanish word. Shows words from the same category, subcategory, and with shared tags. Indicates which the user already knows and which are new. Use when adding a word to suggest building a vocabulary network.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to find related words for (lowercase, infinitive for verbs)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum related words to return (default: 10)"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "generate_contexts",
        "description": "Generate contextual example sentences for a Spanish word/phrase. Claude creates natural sentences in different contexts (conversation, formal, narrative, email, academic). Can be used to enrich existing Anki cards with more examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word or phrase to generate contexts for"
                },
                "context_type": {
                    "type": "string",
                    "enum": ["conversation", "formal", "narrative", "email", "academic"],
                    "description": "Type of context for the sentences (default: conversation)"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of sentences to generate (default: 5)"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "generate_micro_lesson",
        "description": "Generate a targeted 2-3 minute micro-lesson for a specific error pattern. Use when the error journal shows 3+ occurrences of the same error type. Creates a focused lesson with rule explanation, examples, the user's actual mistakes, and practice exercises.",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "The error type from the error journal (e.g., 'gender_agreement', 'ser_vs_estar', 'preterite_vs_imperfect')"
                },
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2"],
                    "description": "CEFR level for the lesson complexity (default: A2)"
                }
            },
            "required": ["error_type"]
        }
    },
    {
        "name": "start_reading_practice",
        "description": "Start a reading practice session. Claude generates a short paragraph (100-150 words) using known vocabulary plus words due for review. This is READ-ONLY - no testing, no comprehension questions. Just reading exposure to reinforce vocabulary in context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Anki deck to pull vocabulary from"
                },
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2"],
                    "description": "CEFR level for the reading passage (default: A2)"
                },
                "topic": {
                    "type": "string",
                    "description": "Optional topic for the passage (e.g., 'daily routine', 'travel', 'food')"
                }
            },
            "required": ["deck_name"]
        }
    },
    {
        "name": "get_grammar_scores",
        "description": "Get per-topic grammar scores across all quiz sessions. Shows percentage per topic with mastery levels: below 70% = needs review, 70-85% = developing, 85%+ = mastered.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_session_due_words",
        "description": "After ANY practice session (translation, quiz, conversation, pair review), get which words from the session are due for Anki review today. Shows words with suggested ease ratings based on session performance, plus time estimates for each ease option. ASKS user to confirm or adjust ratings before marking. NEVER auto-mark.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deck_name": {
                    "type": "string",
                    "description": "Deck to check for due cards"
                },
                "session_words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spanish words encountered during the session"
                },
                "session_results": {
                    "type": "object",
                    "description": "Optional map of word -> result ('correct', 'partial', 'incorrect', 'easy') from the practice session. Used to suggest ease ratings."
                }
            },
            "required": ["deck_name", "session_words"]
        }
    },
    {
        "name": "mark_cards_reviewed",
        "description": "Mark specific cards as reviewed in Anki. ONLY call this AFTER the user explicitly confirms they want to mark cards as reviewed. Never call without user confirmation. Supports per-card ease ratings so the user can choose different ratings for each word.",
        "input_schema": {
            "type": "object",
            "properties": {
                "card_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of card/note IDs to mark as reviewed"
                },
                "ease": {
                    "type": "integer",
                    "description": "Default ease rating for all cards: 1=Again, 2=Hard, 3=Good, 4=Easy (default: 3). Overridden by per_card_ease if provided."
                },
                "per_card_ease": {
                    "type": "object",
                    "description": "Optional per-card ease overrides. Keys are card IDs (strings), values are ease ratings (1-4). Cards not listed here use the default ease."
                },
                "card_words": {
                    "type": "object",
                    "description": "Optional mapping of card ID (string) to the Spanish word on that card. Used for clearer confirmation messages."
                }
            },
            "required": ["card_ids"]
        }
    },
    {
        "name": "batch_delegate",
        "description": "General-purpose batch processing using parallel Claude sub-agents. Process a list of items with a prompt template. Supports delegate types: cognate_scan (classify words by cognate type), network_update (generate word connections), difficulty_score (compute difficulty scores), context_generation (generate practice sentences). Each item is processed independently in parallel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "delegate_type": {
                    "type": "string",
                    "enum": ["cognate_scan", "network_update", "difficulty_score", "context_generation"],
                    "description": "Type of batch processing to perform"
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of items to process (words, phrases, etc.)"
                },
                "prompt_override": {
                    "type": "string",
                    "description": "Optional custom prompt template. Use {item} as placeholder for each item."
                },
                "workers": {
                    "type": "integer",
                    "description": "Parallel workers (default: 5, max: 10)"
                }
            },
            "required": ["delegate_type", "items"]
        }
    },
    {
        "name": "start_conversation_sim",
        "description": "Start a conversation simulation where Claude role-plays a character (waiter, doctor, colleague, etc.) and the user responds in Spanish. Scenarios are tied to CEFR levels. After the conversation, offers to create Anki cards for new vocabulary encountered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "description": "The conversation scenario. A2: ordering_food, asking_directions, hotel_checkin, shopping. B1: job_interview, doctor_visit, phone_call, apartment_rental. B2: debate, negotiation, complaint, storytelling. Or any custom scenario description."
                },
                "level": {
                    "type": "string",
                    "enum": ["A2", "B1", "B2"],
                    "description": "CEFR level for vocabulary and grammar complexity"
                },
                "character": {
                    "type": "string",
                    "description": "The character Claude plays (e.g., 'waiter at a tapas bar', 'doctor', 'job interviewer', 'landlord'). If omitted, a default character is chosen based on the scenario."
                }
            },
            "required": ["scenario", "level"]
        }
    },
    {
        "name": "get_skills_radar",
        "description": "Get a skills radar showing proficiency across 5 dimensions: vocabulary breadth (CEFR coverage), grammar accuracy (quiz scores), productive skill (translation practice scores), topic coverage (themes with learned words), and retention (Anki retention rate). Each dimension is scored 0-100.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_progress_over_time",
        "description": "Get time-based progress showing cards added per week/month, CEFR level progression, and retention rate trends over time. Shows historical snapshots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["week", "month"],
                    "description": "Time grouping: 'week' or 'month' (default: month)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_weak_spots",
        "description": "Get a weak spots dashboard aggregating: grammar topics with lowest quiz scores, vocabulary themes with highest error rates, and most-forgotten Anki cards (high lapses, low ease factor). Use to identify areas needing the most attention.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_study_streaks",
        "description": "Get study streak information: current consecutive-day streak, longest ever streak, last 7 days activity, and total active days.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "record_study_activity",
        "description": "Record study activity for today (or a specific date) to maintain the study streak. Called automatically during practice/quiz sessions but can also be called manually.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (defaults to today)"
                }
            },
            "required": []
        }
    },
    {
        "name": "scan_cognates",
        "description": "Classify a list of Spanish words by cognate type relative to English/French/Romanian. Groups words into: 'transparent' (you probably already recognize these), 'semi_transparent' (close - easy to learn), 'false_friend' (watch out!), and 'none' (need real study). Uses cognate_type data from CEFR vocabulary lists. Great for prioritizing which unknown words to study first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spanish words to classify (lowercase, infinitive for verbs)"
                },
                "level": {
                    "type": "string",
                    "enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
                    "description": "Optional: only scan words at this CEFR level"
                }
            },
            "required": ["words"]
        }
    },
    {
        "name": "check_false_friend",
        "description": "Check if a Spanish word is a known false friend (false cognate with English). Returns the warning and correct meanings if it is. Use this before creating cards to catch false friends that need special warning labels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to check (lowercase)"
                }
            },
            "required": ["word"]
        }
    },
    # -------------------------------------------------------------------
    # Vocabulary Network tools (V1, V3-V11)
    # -------------------------------------------------------------------
    {
        "name": "update_word_network",
        "description": "V1: Update the vocabulary network after adding a card. Claude provides connections (antonyms, synonyms, morphological family, collocations, thematic links, confusables) and the system stores them. Call this AFTER add_card to build the network graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "The Spanish word just added (lowercase, infinitive for verbs)"
                },
                "level": {
                    "type": "string",
                    "description": "CEFR level (e.g., 'A1', 'B2')"
                },
                "pos": {
                    "type": "string",
                    "description": "Part of speech (noun, verb, adjective, adverb, preposition, etc.)"
                },
                "theme": {
                    "type": "string",
                    "description": "Thematic field (e.g., 'food', 'travel', 'health', 'emotions')"
                },
                "connections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["antonym", "morphological", "collocation", "thematic", "synonym", "confusable"],
                                "description": "Connection type"
                            },
                            "target": {
                                "type": "string",
                                "description": "The connected word"
                            },
                            "strength": {
                                "type": "number",
                                "description": "Connection strength 0.0-1.0 (default: 1.0)"
                            }
                        },
                        "required": ["type", "target"]
                    },
                    "description": "List of connections to other words"
                },
                "collocations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phrase": {"type": "string", "description": "The collocation phrase"},
                            "translation": {"type": "string", "description": "English translation"}
                        },
                        "required": ["phrase"]
                    },
                    "description": "Common collocations (V5)"
                },
                "family_root": {
                    "type": "string",
                    "description": "Morphological family root (e.g., 'educar' for 'educacion')"
                },
                "note_id": {
                    "type": "integer",
                    "description": "Anki note ID of the card just added"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "show_word_connections",
        "description": "V1: Show all existing connections for a word in the vocabulary network. Displays synonyms, antonyms, morphological family, collocations, thematic links, and confusables.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to look up (lowercase)"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "get_morphological_family",
        "description": "V3: Find morphological relatives of a Spanish word. Identifies patterns like -cion, -mente, -dor, -able, des-, re- and suggests family members. Example: 'educar' -> educacion, educador, educable, reeducar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to find morphological family for (lowercase)"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "get_disambiguation_practice",
        "description": "V4: Get a disambiguation practice exercise for a confusable pair (INTERNAL practice, not Anki cards). Presents contrast exercises for pairs like ser/estar, saber/conocer, por/para. Tracks errors per pair.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pair": {
                    "type": "string",
                    "description": "Disambiguation pair ID (e.g., 'ser-estar', 'por-para', 'saber-conocer'). Use show_disambiguation_pairs to see all available pairs."
                }
            },
            "required": ["pair"]
        }
    },
    {
        "name": "show_disambiguation_pairs",
        "description": "V4: List all available disambiguation pairs with their practice stats and error counts. Shows which pairs need the most work.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "log_disambiguation_result",
        "description": "V4: Log the result of a disambiguation practice exercise. Records errors and practice count for the pair.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pair_id": {
                    "type": "string",
                    "description": "The disambiguation pair ID (e.g., 'ser-estar')"
                },
                "correct": {
                    "type": "integer",
                    "description": "Number of correct answers"
                },
                "total": {
                    "type": "integer",
                    "description": "Total questions"
                },
                "confused_words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Words the user confused (for error tracking)"
                }
            },
            "required": ["pair_id", "correct", "total"]
        }
    },
    {
        "name": "get_semantic_field_progress",
        "description": "V9: Show vocabulary progress for a specific semantic/thematic field. Shows known vs missing words per theme from CEFR word lists (e.g., 'food_nutrition': 15/30 known).",
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "Theme/category name from CEFR data (e.g., 'food_nutrition', 'travel_transport', 'health_body', 'emotions_feelings'). Omit to see all themes."
                }
            },
            "required": []
        }
    },
    {
        "name": "show_connection_map",
        "description": "V10: Display an ASCII connection map for a word showing all its network relationships (synonyms, antonyms, morphological family, collocations, thematic links). On-demand visualization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Spanish word to map (lowercase)"
                }
            },
            "required": ["word"]
        }
    },
    {
        "name": "start_pair_review",
        "description": "V8: Start a pair-based review session (INTERNAL mode, not Anki cards). Presents antonym/contrast pairs together for comparative practice. Pulls pairs from the vocabulary network.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pair_type": {
                    "type": "string",
                    "enum": ["antonym", "synonym", "confusable", "thematic", "all"],
                    "description": "Type of pairs to review (default: all)"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of pairs to review (default: 5)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_network_study_suggestions",
        "description": "V11: Get study suggestions weighted by network connections to recently-reviewed words. Words connected to what you just reviewed get priority, activating related vocabulary clusters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recently_reviewed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Spanish words recently reviewed (from current or recent Anki session)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum suggestions to return (default: 5)"
                }
            },
            "required": ["recently_reviewed"]
        }
    },
]
