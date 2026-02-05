"""Tests for tools module - tool definitions and schema validation."""

from ankicli.tools import ANKI_TOOLS


class TestToolDefinitions:
    """Tests for ANKI_TOOLS definitions."""

    def test_tools_is_list(self):
        assert isinstance(ANKI_TOOLS, list)

    def test_all_tools_have_required_keys(self):
        for tool in ANKI_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool '{tool.get('name')}' missing 'description'"
            assert "input_schema" in tool, f"Tool '{tool.get('name')}' missing 'input_schema'"

    def test_all_schemas_have_type_object(self):
        for tool in ANKI_TOOLS:
            schema = tool["input_schema"]
            assert schema["type"] == "object", f"Tool '{tool['name']}' schema type is not 'object'"

    def test_all_schemas_have_properties(self):
        for tool in ANKI_TOOLS:
            schema = tool["input_schema"]
            assert "properties" in schema, f"Tool '{tool['name']}' schema missing 'properties'"

    def test_all_schemas_have_required(self):
        for tool in ANKI_TOOLS:
            schema = tool["input_schema"]
            assert "required" in schema, f"Tool '{tool['name']}' schema missing 'required'"
            assert isinstance(schema["required"], list)

    def test_required_fields_exist_in_properties(self):
        for tool in ANKI_TOOLS:
            schema = tool["input_schema"]
            for required_field in schema["required"]:
                assert required_field in schema["properties"], (
                    f"Tool '{tool['name']}': required field '{required_field}' not in properties"
                )

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in ANKI_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"

    def test_tool_names_are_lowercase(self):
        for tool in ANKI_TOOLS:
            assert tool["name"] == tool["name"].lower().replace(" ", "_"), (
                f"Tool name '{tool['name']}' should be lowercase with underscores"
            )

    def test_descriptions_are_not_empty(self):
        for tool in ANKI_TOOLS:
            assert len(tool["description"]) > 10, f"Tool '{tool['name']}' has too short description"


class TestExpectedTools:
    """Tests that expected tools exist."""

    EXPECTED_TOOLS = [
        "list_decks",
        "list_note_types",
        "add_card",
        "add_multiple_cards",
        "search_cards",
        "get_deck_cards",
        "get_note",
        "update_card",
        "update_multiple_cards",
        "delete_cards",
        "add_tags_to_cards",
        "remove_tags_from_cards",
        "move_cards_to_deck",
        "create_deck",
        "sync_anki",
        "get_deck_stats",
        "get_deck_summary",
        "list_deck_fronts",
        "get_collection_stats",
        "check_word_exists",
        "check_words_exist",
        "find_card_by_word",
        "find_cards_by_words",
        "compact_conversation",
        "get_learning_summary",
        "update_learning_summary",
        "set_tool_note",
        "get_tool_notes",
        "remove_tool_note",
        "all_cards_delegate",
        "card_subset_delegate",
    ]

    def test_all_expected_tools_present(self):
        tool_names = {t["name"] for t in ANKI_TOOLS}
        for expected in self.EXPECTED_TOOLS:
            assert expected in tool_names, f"Expected tool '{expected}' not found in ANKI_TOOLS"


class TestAddCardSchema:
    """Tests for add_card tool schema."""

    def _get_tool(self):
        return next(t for t in ANKI_TOOLS if t["name"] == "add_card")

    def test_required_fields(self):
        tool = self._get_tool()
        assert "deck_name" in tool["input_schema"]["required"]
        assert "front" in tool["input_schema"]["required"]
        assert "back" in tool["input_schema"]["required"]

    def test_has_tags_property(self):
        tool = self._get_tool()
        assert "tags" in tool["input_schema"]["properties"]
        tags = tool["input_schema"]["properties"]["tags"]
        assert tags["type"] == "array"

    def test_has_note_type_property(self):
        tool = self._get_tool()
        assert "note_type" in tool["input_schema"]["properties"]


class TestAddMultipleCardsSchema:
    """Tests for add_multiple_cards tool schema."""

    def _get_tool(self):
        return next(t for t in ANKI_TOOLS if t["name"] == "add_multiple_cards")

    def test_required_fields(self):
        tool = self._get_tool()
        assert "deck_name" in tool["input_schema"]["required"]
        assert "cards" in tool["input_schema"]["required"]

    def test_cards_is_array(self):
        tool = self._get_tool()
        cards = tool["input_schema"]["properties"]["cards"]
        assert cards["type"] == "array"
        assert "items" in cards

    def test_card_items_have_required_fields(self):
        tool = self._get_tool()
        items = tool["input_schema"]["properties"]["cards"]["items"]
        assert "front" in items["required"]
        assert "back" in items["required"]


class TestUpdateLearningSchema:
    """Tests for update_learning_summary tool schema."""

    def _get_tool(self):
        return next(t for t in ANKI_TOOLS if t["name"] == "update_learning_summary")

    def test_required_fields(self):
        tool = self._get_tool()
        assert "level" in tool["input_schema"]["required"]
        assert "words_added" in tool["input_schema"]["required"]

    def test_level_has_enum(self):
        tool = self._get_tool()
        level = tool["input_schema"]["properties"]["level"]
        assert "enum" in level
        assert set(level["enum"]) == {"A1", "A2", "B1", "B2"}
