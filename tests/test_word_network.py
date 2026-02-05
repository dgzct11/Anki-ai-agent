"""Tests for word_network module."""

import json
from unittest.mock import patch

from ankicli.word_network import (
    DEFAULT_DISAMBIGUATION_PAIRS,
    DisambiguationPair,
    FALSE_FRIENDS,
    MORPHOLOGICAL_PATTERNS,
    WordConnection,
    WordNetwork,
    WordNode,
    build_connection_map,
    check_false_friend,
    ensure_default_disambiguation,
    get_morphological_family,
)


class TestWordConnection:
    """Tests for WordConnection dataclass."""

    def test_basic(self):
        c = WordConnection(connection_type="synonym", target_word="casa")
        assert c.connection_type == "synonym"
        assert c.target_word == "casa"
        assert c.strength == 1.0

    def test_custom_strength(self):
        c = WordConnection(connection_type="thematic", target_word="perro", strength=0.5)
        assert c.strength == 0.5


class TestWordNode:
    """Tests for WordNode dataclass."""

    def test_basic(self):
        node = WordNode(word="gato", level="A1", pos="noun", theme="animals")
        assert node.word == "gato"
        assert node.level == "A1"
        assert node.family_root is None
        assert node.in_deck is False
        assert node.note_id is None
        assert node.connections == []
        assert node.collocations == []
        assert node.disambiguation_group is None

    def test_with_connections(self):
        conn = WordConnection(connection_type="antonym", target_word="perro")
        node = WordNode(
            word="gato", level="A1", pos="noun", theme="animals",
            connections=[conn],
        )
        assert len(node.connections) == 1
        assert node.connections[0].target_word == "perro"


class TestDisambiguationPair:
    """Tests for DisambiguationPair dataclass."""

    def test_basic(self):
        pair = DisambiguationPair(
            pair_id="ser-estar",
            words=["ser", "estar"],
            category="verb_usage",
        )
        assert pair.pair_id == "ser-estar"
        assert pair.words == ["ser", "estar"]
        assert pair.error_counts == {}

    def test_with_error_counts(self):
        pair = DisambiguationPair(
            pair_id="ser-estar",
            words=["ser", "estar"],
            category="verb_usage",
            error_counts={"ser_for_estar": 3, "estar_for_ser": 1},
        )
        assert pair.error_counts["ser_for_estar"] == 3


def _patch_network_paths(tmp_path):
    """Create patches for word_network module paths."""
    data_dir = tmp_path / ".ankicli"
    network_file = data_dir / "word_network.json"
    disambig_file = data_dir / "disambiguation.json"
    return (
        patch("ankicli.word_network.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.word_network.WORD_NETWORK_FILE", network_file),
        patch("ankicli.word_network.DISAMBIGUATION_FILE", disambig_file),
        network_file,
        disambig_file,
    )


class TestWordNetwork:
    """Tests for WordNetwork class."""

    def test_empty_network(self):
        net = WordNetwork()
        assert net.word_count == 0
        assert net.disambiguation_count == 0

    def test_add_word(self):
        net = WordNetwork()
        node = WordNode(word="gato", level="A1", pos="noun", theme="animals")
        net.add_word(node)
        assert net.word_count == 1
        assert net.get_node("gato") is node

    def test_get_node_case_insensitive(self):
        net = WordNetwork()
        node = WordNode(word="Gato", level="A1", pos="noun", theme="animals")
        net.add_word(node)
        assert net.get_node("gato") is node
        assert net.get_node("GATO") is node

    def test_get_node_not_found(self):
        net = WordNetwork()
        assert net.get_node("nonexistent") is None

    def test_get_connections(self):
        net = WordNetwork()
        conns = [
            WordConnection(connection_type="synonym", target_word="hogar"),
            WordConnection(connection_type="antonym", target_word="calle"),
        ]
        node = WordNode(word="casa", level="A1", pos="noun", theme="housing", connections=conns)
        net.add_word(node)

        all_conns = net.get_connections("casa")
        assert len(all_conns) == 2

        synonyms = net.get_connections("casa", connection_type="synonym")
        assert len(synonyms) == 1
        assert synonyms[0].target_word == "hogar"

    def test_get_connections_not_found(self):
        net = WordNetwork()
        assert net.get_connections("nonexistent") == []

    def test_get_family(self):
        net = WordNetwork()
        net.add_word(WordNode(word="libro", level="A1", pos="noun", theme="education", family_root="libr"))
        net.add_word(WordNode(word="librería", level="A2", pos="noun", theme="shopping", family_root="libr"))
        net.add_word(WordNode(word="librero", level="B1", pos="noun", theme="education", family_root="libr"))
        net.add_word(WordNode(word="gato", level="A1", pos="noun", theme="animals", family_root="gat"))

        family = net.get_family("libro")
        assert len(family) == 3
        family_words = {n.word for n in family}
        assert family_words == {"libro", "librería", "librero"}

    def test_get_family_no_root(self):
        net = WordNetwork()
        node = WordNode(word="hola", level="A1", pos="interjection", theme="greetings")
        net.add_word(node)
        family = net.get_family("hola")
        assert len(family) == 1
        assert family[0].word == "hola"

    def test_get_family_not_found(self):
        net = WordNetwork()
        assert net.get_family("nonexistent") == []

    def test_get_semantic_field(self):
        net = WordNetwork()
        net.add_word(WordNode(word="gato", level="A1", pos="noun", theme="animals"))
        net.add_word(WordNode(word="perro", level="A1", pos="noun", theme="animals"))
        net.add_word(WordNode(word="casa", level="A1", pos="noun", theme="housing"))

        field = net.get_semantic_field("gato")
        assert len(field) == 2
        words = {n.word for n in field}
        assert words == {"gato", "perro"}

    def test_get_semantic_field_not_found(self):
        net = WordNetwork()
        assert net.get_semantic_field("nonexistent") == []

    def test_add_disambiguation_pair(self):
        net = WordNetwork()
        pair = DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"], category="verb_usage")
        net.add_disambiguation_pair(pair)
        assert net.disambiguation_count == 1

    def test_get_disambiguation_pairs_all(self):
        net = WordNetwork()
        net.add_disambiguation_pair(DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"]))
        net.add_disambiguation_pair(DisambiguationPair(pair_id="por-para", words=["por", "para"]))

        pairs = net.get_disambiguation_pairs()
        assert len(pairs) == 2

    def test_get_disambiguation_pairs_for_word(self):
        net = WordNetwork()
        net.add_disambiguation_pair(DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"]))
        net.add_disambiguation_pair(DisambiguationPair(pair_id="por-para", words=["por", "para"]))

        pairs = net.get_disambiguation_pairs("ser")
        assert len(pairs) == 1
        assert pairs[0].pair_id == "ser-estar"

    def test_get_disambiguation_pairs_not_found(self):
        net = WordNetwork()
        pairs = net.get_disambiguation_pairs("nonexistent")
        assert pairs == []


class TestWordNetworkPersistence:
    """Tests for save/load cycle."""

    def test_save_and_load(self, tmp_path):
        p1, p2, p3, nf, df = _patch_network_paths(tmp_path)
        with p1, p2, p3:
            net = WordNetwork()
            net.add_word(WordNode(
                word="gato", level="A1", pos="noun", theme="animals",
                family_root="gat", in_deck=True, note_id=12345,
                connections=[WordConnection(connection_type="antonym", target_word="perro", strength=0.8)],
                collocations=[{"phrase": "el gato negro", "frequency": "high"}],
                disambiguation_group="animals",
            ))
            net.add_disambiguation_pair(DisambiguationPair(
                pair_id="ser-estar", words=["ser", "estar"],
                category="verb_usage", error_counts={"wrong": 2},
            ))
            net.save()

            # Load into a new network
            net2 = WordNetwork()
            net2.load()

            assert net2.word_count == 1
            node = net2.get_node("gato")
            assert node is not None
            assert node.word == "gato"
            assert node.level == "A1"
            assert node.family_root == "gat"
            assert node.in_deck is True
            assert node.note_id == 12345
            assert len(node.connections) == 1
            assert node.connections[0].connection_type == "antonym"
            assert node.connections[0].strength == 0.8
            assert len(node.collocations) == 1
            assert node.disambiguation_group == "animals"

            pairs = net2.get_disambiguation_pairs()
            assert len(pairs) == 1
            assert pairs[0].pair_id == "ser-estar"
            assert pairs[0].error_counts == {"wrong": 2}

    def test_load_empty(self, tmp_path):
        p1, p2, p3, nf, df = _patch_network_paths(tmp_path)
        with p1, p2, p3:
            net = WordNetwork()
            net.load()  # No files exist
            assert net.word_count == 0
            assert net.disambiguation_count == 0

    def test_load_corrupt_json(self, tmp_path):
        p1, p2, p3, nf, df = _patch_network_paths(tmp_path)
        with p1, p2, p3:
            nf.parent.mkdir(parents=True, exist_ok=True)
            nf.write_text("{bad json")
            df.write_text("{bad json")

            net = WordNetwork()
            net.load()
            assert net.word_count == 0
            assert net.disambiguation_count == 0

    def test_save_creates_files(self, tmp_path):
        p1, p2, p3, nf, df = _patch_network_paths(tmp_path)
        with p1, p2, p3:
            net = WordNetwork()
            net.save()
            assert nf.exists()
            assert df.exists()

            # Verify JSON is valid
            data = json.loads(nf.read_text())
            assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Tests for add_connection (bidirectional)
# ---------------------------------------------------------------------------

class TestAddConnection:
    """Tests for WordNetwork.add_connection."""

    def test_bidirectional(self):
        net = WordNetwork()
        net.add_connection("bueno", "malo", "antonym")

        conns_bueno = net.get_connections("bueno")
        conns_malo = net.get_connections("malo")
        assert len(conns_bueno) == 1
        assert conns_bueno[0].target_word == "malo"
        assert len(conns_malo) == 1
        assert conns_malo[0].target_word == "bueno"

    def test_no_duplicate_connections(self):
        net = WordNetwork()
        net.add_connection("bueno", "malo", "antonym")
        net.add_connection("bueno", "malo", "antonym")

        conns = net.get_connections("bueno")
        assert len(conns) == 1

    def test_creates_stub_nodes(self):
        net = WordNetwork()
        net.add_connection("new1", "new2", "thematic")

        assert net.get_node("new1") is not None
        assert net.get_node("new2") is not None

    def test_custom_strength(self):
        net = WordNetwork()
        net.add_connection("a", "b", "synonym", strength=0.7)

        conns = net.get_connections("a")
        assert conns[0].strength == 0.7


class TestAddCollocation:
    """Tests for WordNetwork.add_collocation."""

    def test_add_collocation(self):
        net = WordNetwork()
        net.add_word(WordNode(word="hacer", level="A1", pos="verb", theme="general"))
        net.add_collocation("hacer", "hacer falta", "to be needed")

        node = net.get_node("hacer")
        assert len(node.collocations) == 1
        assert node.collocations[0]["phrase"] == "hacer falta"
        assert node.collocations[0]["translation"] == "to be needed"

    def test_no_duplicate_collocation(self):
        net = WordNetwork()
        net.add_collocation("hacer", "hacer falta", "to be needed")
        net.add_collocation("hacer", "hacer falta", "to be needed")

        node = net.get_node("hacer")
        assert len(node.collocations) == 1

    def test_creates_stub_node(self):
        net = WordNetwork()
        net.add_collocation("new_word", "new_word algo", "something")

        assert net.get_node("new_word") is not None


class TestDisambiguationTracking:
    """Tests for disambiguation error and practice recording."""

    def test_record_practice(self):
        net = WordNetwork()
        pair = DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"])
        net.add_disambiguation_pair(pair)

        net.record_disambiguation_practice("ser-estar")
        assert pair.practice_count == 1
        assert pair.last_practiced != ""

    def test_record_error(self):
        net = WordNetwork()
        pair = DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"])
        net.add_disambiguation_pair(pair)

        net.record_disambiguation_error("ser-estar", "ser")
        net.record_disambiguation_error("ser-estar", "ser")
        net.record_disambiguation_error("ser-estar", "estar")

        assert pair.error_counts["ser"] == 2
        assert pair.error_counts["estar"] == 1

    def test_record_nonexistent_pair(self):
        net = WordNetwork()
        # Should not raise
        net.record_disambiguation_practice("nonexistent")
        net.record_disambiguation_error("nonexistent", "word")


class TestGetRecentlyConnected:
    """Tests for WordNetwork.get_recently_connected."""

    def test_depth_1(self):
        net = WordNetwork()
        net.add_connection("a", "b", "synonym")
        net.add_connection("b", "c", "synonym")
        net.add_connection("c", "d", "synonym")

        result = net.get_recently_connected("a", depth=1)
        assert "b" in result
        assert "c" not in result

    def test_depth_2(self):
        net = WordNetwork()
        net.add_connection("a", "b", "synonym")
        net.add_connection("b", "c", "synonym")
        net.add_connection("c", "d", "synonym")

        result = net.get_recently_connected("a", depth=2)
        assert "b" in result
        assert "c" in result
        assert "d" not in result
        assert "a" not in result  # Source excluded

    def test_no_connections(self):
        net = WordNetwork()
        net.add_word(WordNode(word="lonely", level="A1", pos="adj", theme=""))
        result = net.get_recently_connected("lonely")
        assert result == []


class TestGetNetworkSuggestions:
    """Tests for V11: spaced network activation."""

    def test_suggestions_from_connections(self):
        net = WordNetwork()
        net.add_word(WordNode(word="bueno", level="A1", pos="adj", theme="qualities", in_deck=True))
        net.add_word(WordNode(word="malo", level="A1", pos="adj", theme="qualities", in_deck=True))
        net.add_word(WordNode(word="bien", level="A1", pos="adv", theme="qualities", in_deck=True))

        net.add_connection("bueno", "malo", "antonym")
        net.add_connection("bueno", "bien", "morphological")

        suggestions = net.get_network_suggestions(["bueno"], limit=5)
        assert "malo" in suggestions
        assert "bien" in suggestions
        assert "bueno" not in suggestions  # Recently reviewed excluded

    def test_no_suggestions_empty_network(self):
        net = WordNetwork()
        suggestions = net.get_network_suggestions(["random"])
        assert suggestions == []

    def test_only_in_deck_words(self):
        net = WordNetwork()
        net.add_word(WordNode(word="a", level="A1", pos="n", theme="", in_deck=True))
        net.add_word(WordNode(word="b", level="A1", pos="n", theme="", in_deck=False))

        net.add_connection("x", "a", "thematic")
        net.add_connection("x", "b", "thematic")

        suggestions = net.get_network_suggestions(["x"], limit=5)
        assert "a" in suggestions
        assert "b" not in suggestions  # Not in deck


# ---------------------------------------------------------------------------
# Tests for morphological family (V3)
# ---------------------------------------------------------------------------

class TestMorphologicalFamily:
    """Tests for get_morphological_family."""

    def test_verb_to_noun_cion(self):
        result = get_morphological_family("educar")
        assert "educacion" in result["family"]

    def test_noun_cion_to_verb(self):
        result = get_morphological_family("educacion")
        assert "educar" in result["family"]

    def test_adjective_to_adverb_mente(self):
        result = get_morphological_family("rapido")
        assert "rapidomente" in result["family"] or any("mente" in w for w in result["family"])

    def test_prefix_des(self):
        result = get_morphological_family("conocido")
        assert "desconocido" in result["family"]

    def test_prefix_re(self):
        result = get_morphological_family("hacer")
        assert "rehacer" in result["family"]

    def test_with_network_family(self):
        net = WordNetwork()
        net.add_word(WordNode(word="educar", level="A2", pos="verb", theme="education"))
        net.add_connection("educar", "educativo", "morphological")

        result = get_morphological_family("educar", network=net)
        assert "educativo" in result["network_family"]
        assert "educativo" in result["family"]

    def test_unknown_word(self):
        result = get_morphological_family("xyz")
        # Should still produce derivations even for unknown words
        assert isinstance(result["family"], list)
        assert isinstance(result["patterns_matched"], list)

    def test_patterns_not_empty(self):
        assert len(MORPHOLOGICAL_PATTERNS) > 0
        for pat in MORPHOLOGICAL_PATTERNS:
            assert "description" in pat
            assert "suffix" in pat or "prefix" in pat


# ---------------------------------------------------------------------------
# Tests for false friends (V6)
# ---------------------------------------------------------------------------

class TestFalseFriends:
    """Tests for check_false_friend."""

    def test_known_false_friend(self):
        result = check_false_friend("embarazada")
        assert result is not None
        assert result["actual"] == "pregnant"
        assert result["false_english"] == "embarrassed"

    def test_not_false_friend(self):
        result = check_false_friend("gato")
        assert result is None

    def test_case_insensitive(self):
        result = check_false_friend("EMBARAZADA")
        assert result is not None

    def test_all_false_friends_have_required_keys(self):
        for ff in FALSE_FRIENDS:
            assert "spanish" in ff
            assert "false_english" in ff
            assert "actual" in ff

    def test_false_friends_count(self):
        assert len(FALSE_FRIENDS) >= 15  # We defined at least 15


# ---------------------------------------------------------------------------
# Tests for default disambiguation pairs
# ---------------------------------------------------------------------------

class TestDefaultDisambiguation:
    """Tests for default disambiguation pairs."""

    def test_defaults_exist(self):
        assert len(DEFAULT_DISAMBIGUATION_PAIRS) >= 10

    def test_ser_estar_in_defaults(self):
        ids = [p.pair_id for p in DEFAULT_DISAMBIGUATION_PAIRS]
        assert "ser-estar" in ids
        assert "por-para" in ids
        assert "saber-conocer" in ids

    def test_ensure_default_disambiguation(self):
        net = WordNetwork()
        ensure_default_disambiguation(net)
        assert net.disambiguation_count >= 10
        assert net._disambiguation.get("ser-estar") is not None

    def test_ensure_does_not_overwrite(self):
        net = WordNetwork()
        custom = DisambiguationPair(pair_id="ser-estar", words=["ser", "estar"],
                                    category="custom", practice_count=5)
        net.add_disambiguation_pair(custom)
        ensure_default_disambiguation(net)

        pair = net._disambiguation["ser-estar"]
        assert pair.category == "custom"
        assert pair.practice_count == 5


# ---------------------------------------------------------------------------
# Tests for ASCII connection map (V10)
# ---------------------------------------------------------------------------

class TestConnectionMap:
    """Tests for build_connection_map."""

    def test_word_not_found(self):
        net = WordNetwork()
        result = build_connection_map("nonexistent", net)
        assert "not found" in result

    def test_no_connections(self):
        net = WordNetwork()
        net.add_word(WordNode(word="solo", level="A1", pos="adj", theme=""))
        result = build_connection_map("solo", net)
        assert "no connections" in result

    def test_with_connections(self):
        net = WordNetwork()
        net.add_word(WordNode(word="bueno", level="A1", pos="adj", theme="qualities"))
        net.add_connection("bueno", "malo", "antonym")
        net.add_connection("bueno", "bien", "morphological")

        result = build_connection_map("bueno", net)
        assert "BUENO" in result
        assert "antonym" in result
        assert "malo" in result
        assert "morphological" in result
        assert "bien" in result

    def test_with_collocations(self):
        net = WordNetwork()
        net.add_word(WordNode(word="hacer", level="A1", pos="verb", theme="general"))
        net.add_collocation("hacer", "hacer falta", "to be needed")

        result = build_connection_map("hacer", net)
        assert "collocations" in result
        assert "hacer falta" in result

    def test_deck_marker(self):
        net = WordNetwork()
        net.add_word(WordNode(word="a", level="A1", pos="n", theme="", in_deck=True))
        net.add_word(WordNode(word="b", level="A1", pos="n", theme="", in_deck=False))
        net.add_connection("a", "b", "synonym")

        result = build_connection_map("a", net)
        assert "Legend: * = in Anki deck" in result
