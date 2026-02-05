# Anki AI Agent

An AI-powered command-line agent that manages your Anki flashcards through natural conversation. Powered by Claude, it autonomously decides which tools to use, chains operations together, and handles complex card management tasks.

Perfect for language learning, med school, law school, or any subject where spaced repetition helps.

## Features

### Agentic AI
- **Autonomous Decision Making**: Claude decides which tools to use based on your request
- **Tool Chaining**: Automatically chains multiple operations (e.g., check for duplicates → add cards → update progress)
- **Context Awareness**: Remembers conversation history and your preferences across sessions

### Rich Terminal UI
- **Live Feedback**: Spinners show when Claude is thinking
- **Tool Panels**: See exactly what operations are being performed
- **Markdown Rendering**: Responses are beautifully formatted
- **Progress Bars**: Visual context window usage indicator

### Smart Card Management
- **Bulk Operations**: Add 10, 20, or 50+ cards in a single request
- **Duplicate Detection**: Automatically checks for existing cards before adding
- **HTML Formatting**: Cards are formatted with bold, italic, and line breaks
- **Tag Management**: Add, remove, and search by tags

## Demo

```
╭─────────────────────────────────────────────────────────────────╮
│ Anki Assistant                                                  │
│                                                                 │
│ Chat with Claude to manage your Anki flashcards.                │
╰─────────────────────────────────────────────────────────────────╯

You: Add 5 common French verbs for cooking

⠋ Thinking...

╭──────────────── Tool Call ─────────────────╮
│ check_words_exist                          │
│   words: 5 items                           │
│   deck_name: French Vocab                  │
╰────────────────────────────────────────────╯
╭──────────── Result: check_words_exist ─────────────╮
│ NOT FOUND - safe to add (5): cuire, mélanger,      │
│ couper, assaisonner, faire revenir                 │
╰────────────────────────────────────────────────────╯

╭──────────────── Tool Call ─────────────────╮
│ add_multiple_cards                         │
│   deck_name: French Vocab                  │
│   cards: 5 items                           │
╰────────────────────────────────────────────╯
╭──────────── Result: add_multiple_cards ────────────╮
│ Added 5/5 cards successfully                       │
╰────────────────────────────────────────────────────╯
```

## Available Tools

The agent has access to 20+ tools for managing your Anki collection:

| Tool | Description |
|------|-------------|
| `list_decks` | List all decks with card counts |
| `add_card` | Add a single card |
| `add_multiple_cards` | Bulk add cards (10, 20, 50+) |
| `search_cards` | Search with Anki query syntax |
| `update_card` | Edit a card's content |
| `delete_cards` | Remove cards |
| `check_word_exists` | Check for duplicates before adding |
| `check_words_exist` | Bulk duplicate check |
| `get_deck_summary` | Get deck statistics |
| `create_deck` | Create new decks |
| `sync_anki` | Sync with AnkiWeb |
| `get_learning_summary` | View learning progress |
| `update_learning_summary` | Track progress by topic |

## Prerequisites

### 1. Anki Desktop

Download and install Anki from [https://apps.ankiweb.net/](https://apps.ankiweb.net/)

### 2. AnkiConnect Add-on

AnkiConnect provides the local API that allows this tool to communicate with Anki.

1. Open Anki
2. Go to **Tools → Add-ons → Get Add-ons...**
3. Enter the code: `2055492159`
4. Click **OK** and restart Anki

**Verify it's working:** Visit [http://localhost:8765](http://localhost:8765) in your browser - you should see "AnkiConnect" or a JSON response.

> **Note:** Anki must be running whenever you use this tool.

### 3. Claude API Key

Get your API key from [https://console.anthropic.com/](https://console.anthropic.com/)

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/dgzct11/Anki-ai-agent.git
cd Anki-ai-agent

# Create virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/dgzct11/Anki-ai-agent.git
cd Anki-ai-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install
pip install -e .
```

## Configuration

Create a `.env` file in the project root with your API key:

```bash
ANTHROPIC_API_KEY=your-api-key-here
```

Or copy from the example:

```bash
cp .env.example .env
# Then edit .env with your API key
```

## Usage

Make sure **Anki is running**, then start the assistant:

```bash
ankicli chat
```

### Chat Commands

| Command | Description |
|---------|-------------|
| `history` | Show recent chat exchanges with tool summaries |
| `progress` | Show learning progress summary |
| `status` | Show context window usage |
| `compact` | Summarize old messages to free up context |
| `clear` / `new` | Reset conversation (start fresh) |
| `exit` | Quit |

### Example Conversations

**Adding cards:**
```
You: Add 10 vocabulary cards for French cooking terms
You: Create flashcards for the amendments in the Bill of Rights
You: Add cards for the Krebs cycle
```

**Managing cards:**
```
You: Show me my decks
You: Search for cards tagged "chapter-5"
You: Delete duplicate cards in my Biology deck
You: Update the card about mitochondria
```

**Bulk operations:**
```
You: Add 20 cards for Japanese JLPT N5 vocabulary
You: Create a deck of medical terminology for cardiology
```

## Data Storage

All data is stored in the `.ankicli/` directory:

| File | Purpose |
|------|---------|
| `conversation.json` | Claude's conversation context (compactable) |
| `chat_log.json` | Readable history of all exchanges |
| `learning_summary.json` | Learning progress tracking |
| `chat_history` | Command-line input recall (↑ arrow) |

## Troubleshooting

**"Cannot connect to Anki"**
- Make sure Anki desktop is running
- Check that AnkiConnect is installed (Tools → Add-ons)
- Verify [http://localhost:8765](http://localhost:8765) responds

**"ANTHROPIC_API_KEY not set"**
- Create a `.env` file with your API key
- Or export it: `export ANTHROPIC_API_KEY=your-key`

**Cards not syncing to AnkiWeb**
- Run `ankicli sync` or ask the assistant to sync
- Or sync manually in Anki (Tools → Sync)

## License

MIT