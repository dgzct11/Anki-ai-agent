"""Persistent learning summary storage."""

import json
from datetime import datetime
from pathlib import Path

SUMMARY_DIR = Path(__file__).parent.parent.parent / ".ankicli"
SUMMARY_FILE = SUMMARY_DIR / "learning_summary.json"


def _ensure_dir():
    """Ensure the config directory exists."""
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


def get_default_summary() -> dict:
    """Return a default empty summary structure."""
    return {
        "last_updated": None,
        "total_cards_added": 0,
        "levels": {
            "A1": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Basic greetings, introductions, numbers 1-100, colors, days/months, telling time, basic present tense verbs (ser, estar, tener, ir), simple questions, basic pronouns",
                    "vocabulary_gaps": ["greetings", "numbers", "colors", "days", "months", "basic-verbs", "pronouns", "family", "common-objects"],
                    "grammar_gaps": ["Present tense regular verbs", "Ser vs Estar basics", "Gender and number agreement", "Basic question formation"],
                    "priority_topics": ["Self-introduction", "Basic conversation", "Numbers and time", "Common everyday objects"]
                },
                "estimated_coverage": 0
            },
            "A2": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Everyday vocabulary for routine activities, past tense (preterite/imperfect), reflexive verbs, direct/indirect object pronouns, comparisons, basic connectors",
                    "vocabulary_gaps": ["daily-routine", "food", "travel", "work", "health", "emotions", "directions", "shopping"],
                    "grammar_gaps": ["Preterite tense", "Imperfect tense", "Reflexive verbs", "Object pronouns", "Comparatives/superlatives"],
                    "priority_topics": ["Daily routines", "Restaurant/food", "Travel basics", "Describing past events"]
                },
                "estimated_coverage": 0
            },
            "B1": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Subjunctive mood (present), conditional tense, future tense, relative clauses, advanced connectors, abstract vocabulary, opinions and hypotheticals",
                    "vocabulary_gaps": ["abstract-concepts", "opinions", "media", "environment", "politics", "culture", "idioms"],
                    "grammar_gaps": ["Present subjunctive", "Conditional tense", "Future tense", "Relative pronouns", "Subjunctive triggers"],
                    "priority_topics": ["Expressing opinions", "Hypothetical situations", "News and media", "Cultural topics"]
                },
                "estimated_coverage": 0
            },
            "B2": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Imperfect subjunctive, conditional perfect, passive voice, advanced idiomatic expressions, nuanced vocabulary, formal/informal register",
                    "vocabulary_gaps": ["professional", "academic", "nuanced-expressions", "regional-variations", "advanced-idioms"],
                    "grammar_gaps": ["Imperfect subjunctive", "Conditional perfect", "Passive constructions", "Sequence of tenses", "Advanced clause structures"],
                    "priority_topics": ["Professional communication", "Academic discourse", "Nuanced argumentation", "Literary and formal styles"]
                },
                "estimated_coverage": 0
            }
        },
        "recent_additions": [],
        "notes": ""
    }


def load_summary() -> dict:
    """Load the learning summary from disk."""
    _ensure_dir()
    if not SUMMARY_FILE.exists():
        return get_default_summary()
    try:
        with open(SUMMARY_FILE) as f:
            data = json.load(f)
            # Migrate old format to new format if needed
            if data.get("levels") and "what_i_know" not in data["levels"].get("A1", {}):
                return get_default_summary()
            return data
    except (json.JSONDecodeError, IOError):
        return get_default_summary()


def save_summary(summary: dict) -> None:
    """Save the learning summary to disk."""
    _ensure_dir()
    summary["last_updated"] = datetime.now().isoformat()
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def format_summary_for_display(summary: dict) -> str:
    """Format the summary for readable display."""
    output = []
    output.append("=" * 70)
    output.append("SPANISH LEARNING PROGRESS SUMMARY")
    output.append("=" * 70)

    if summary.get("last_updated"):
        output.append(f"Last updated: {summary['last_updated'][:16].replace('T', ' ')}")
    output.append(f"Total cards added: {summary.get('total_cards_added', 0)}")
    output.append("")

    # Level breakdown
    for level in ["A1", "A2", "B1", "B2"]:
        data = summary.get("levels", {}).get(level, {})
        coverage = data.get("estimated_coverage", 0)
        bar_width = 20
        filled = int(bar_width * coverage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        output.append(f"{'─' * 70}")
        output.append(f"  {level}: [{bar}] {coverage}%")
        output.append(f"{'─' * 70}")

        # What I know
        what_i_know = data.get("what_i_know", {})
        if what_i_know.get("summary"):
            output.append("")
            output.append(f"  WHAT I KNOW:")
            # Word wrap the summary
            summary_text = what_i_know["summary"]
            words = summary_text.split()
            line = "    "
            for word in words:
                if len(line) + len(word) + 1 > 68:
                    output.append(line)
                    line = "    " + word
                else:
                    line = line + " " + word if line.strip() else "    " + word
            if line.strip():
                output.append(line)

            # Show vocabulary count
            vocab = what_i_know.get("vocabulary", [])
            if vocab:
                output.append(f"    Vocabulary: {len(vocab)} words")

            # Show grammar concepts
            grammar = what_i_know.get("grammar_concepts", [])
            if grammar:
                output.append(f"    Grammar: {', '.join(grammar)}")

            # Show topics
            topics = what_i_know.get("topics_covered", [])
            if topics:
                output.append(f"    Topics: {', '.join(topics)}")

        # What to learn
        what_to_learn = data.get("what_to_learn", {})
        if what_to_learn.get("summary") or what_to_learn.get("priority_topics"):
            output.append("")
            output.append(f"  WHAT TO LEARN:")
            if what_to_learn.get("summary"):
                summary_text = what_to_learn["summary"]
                words = summary_text.split()
                line = "    "
                for word in words:
                    if len(line) + len(word) + 1 > 68:
                        output.append(line)
                        line = "    " + word
                    else:
                        line = line + " " + word if line.strip() else "    " + word
                if line.strip():
                    output.append(line)

            # Show vocabulary gaps
            vocab_gaps = what_to_learn.get("vocabulary_gaps", [])
            if vocab_gaps:
                output.append(f"    Missing vocab: {', '.join(vocab_gaps[:5])}")

            # Show grammar gaps
            grammar_gaps = what_to_learn.get("grammar_gaps", [])
            if grammar_gaps:
                output.append(f"    Missing grammar: {', '.join(grammar_gaps[:3])}")

            # Show priority topics
            priority = what_to_learn.get("priority_topics", [])
            if priority:
                output.append(f"    Priority: {', '.join(priority[:3])}")

        output.append("")

    # Recent additions
    if summary.get("recent_additions"):
        output.append("RECENT ADDITIONS:")
        output.append("-" * 40)
        recent = summary["recent_additions"][-15:]
        # Show in rows of 5
        for i in range(0, len(recent), 5):
            chunk = recent[i:i+5]
            output.append("  " + ", ".join(chunk))
        output.append("")

    # Notes
    if summary.get("notes"):
        output.append("NOTES:")
        output.append("-" * 40)
        output.append(summary["notes"])

    output.append("=" * 70)
    return "\n".join(output)
