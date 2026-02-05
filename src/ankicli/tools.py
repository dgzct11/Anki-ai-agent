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
    }
]
