# tests/test_query_parser.py

"""Tests for the boolean query parser, DNF expansion, and AST evaluator."""

import unittest

from src.filters.query_parser import (
    AndNode,
    OrNode,
    PhraseNode,
    QueryPlanner,
    TermNode,
    Token,
    TokenType,
    has_boolean_syntax,
    local_evaluate,
    tokenize,
)


# ── Tokenizer ────────────────────────────────────────────


class TestTokenizer(unittest.TestCase):
    """Tokenize raw query strings."""

    def test_simple_words(self) -> None:
        """Bare words become WORD tokens."""
        tokens = tokenize("collagen powder")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0], Token(TokenType.WORD, "collagen"))
        self.assertEqual(tokens[1], Token(TokenType.WORD, "powder"))

    def test_quoted_phrase(self) -> None:
        """Double-quoted strings become PHRASE tokens."""
        tokens = tokenize('"multi collagen"')
        self.assertEqual(len(tokens), 1)
        self.assertEqual(
            tokens[0], Token(TokenType.PHRASE, "multi collagen")
        )

    def test_and_or_keywords(self) -> None:
        """AND / OR (case-insensitive) become keyword tokens."""
        tokens = tokenize("a AND b or c")
        types = [t.type for t in tokens]
        self.assertEqual(
            types,
            [
                TokenType.WORD,
                TokenType.AND,
                TokenType.WORD,
                TokenType.OR,
                TokenType.WORD,
            ],
        )

    def test_parens(self) -> None:
        """Parentheses tokenize correctly."""
        tokens = tokenize("(a OR b)")
        types = [t.type for t in tokens]
        self.assertEqual(
            types,
            [
                TokenType.LPAREN,
                TokenType.WORD,
                TokenType.OR,
                TokenType.WORD,
                TokenType.RPAREN,
            ],
        )

    def test_negation(self) -> None:
        """Leading dash produces NEGATION tokens."""
        tokens = tokenize("collagen -serum -mask")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].type, TokenType.WORD)
        self.assertEqual(tokens[1], Token(TokenType.NEGATION, "serum"))
        self.assertEqual(tokens[2], Token(TokenType.NEGATION, "mask"))

    def test_mixed_complex(self) -> None:
        """Complex mixed input tokenizes all types."""
        raw = '("multi collagen" OR peptides) AND powder -serum'
        tokens = tokenize(raw)
        types = [t.type for t in tokens]
        self.assertEqual(
            types,
            [
                TokenType.LPAREN,
                TokenType.PHRASE,
                TokenType.OR,
                TokenType.WORD,
                TokenType.RPAREN,
                TokenType.AND,
                TokenType.WORD,
                TokenType.NEGATION,
            ],
        )

    def test_empty_string(self) -> None:
        """Empty input produces no tokens."""
        self.assertEqual(tokenize(""), [])


# ── Parser ───────────────────────────────────────────────


class TestParser(unittest.TestCase):
    """Parse token streams into ASTs."""

    def test_single_term(self) -> None:
        """A single word parses to a TermNode."""
        plan = QueryPlanner.parse("collagen")
        self.assertIsInstance(plan.ast, TermNode)
        assert isinstance(plan.ast, TermNode)
        self.assertEqual(plan.ast.value, "collagen")

    def test_single_phrase(self) -> None:
        """A quoted phrase parses to a PhraseNode."""
        plan = QueryPlanner.parse('"multi collagen"')
        self.assertIsInstance(plan.ast, PhraseNode)
        assert isinstance(plan.ast, PhraseNode)
        self.assertEqual(plan.ast.value, "multi collagen")

    def test_implicit_and(self) -> None:
        """Adjacent terms are joined by implicit AND."""
        plan = QueryPlanner.parse("collagen powder")
        self.assertIsInstance(plan.ast, AndNode)
        assert isinstance(plan.ast, AndNode)
        self.assertEqual(len(plan.ast.children), 2)

    def test_explicit_and(self) -> None:
        """Explicit AND keyword joins terms."""
        plan = QueryPlanner.parse("collagen AND powder")
        self.assertIsInstance(plan.ast, AndNode)

    def test_or(self) -> None:
        """OR keyword creates an OrNode."""
        plan = QueryPlanner.parse("collagen OR peptides")
        self.assertIsInstance(plan.ast, OrNode)
        assert isinstance(plan.ast, OrNode)
        self.assertEqual(len(plan.ast.children), 2)

    def test_parens_grouping(self) -> None:
        """Parentheses change grouping."""
        plan = QueryPlanner.parse(
            "(collagen OR peptides) AND powder"
        )
        self.assertIsInstance(plan.ast, AndNode)
        assert isinstance(plan.ast, AndNode)
        self.assertIsInstance(plan.ast.children[0], OrNode)
        self.assertIsInstance(plan.ast.children[1], TermNode)

    def test_negatives_extracted(self) -> None:
        """Trailing -keywords are extracted as global negatives."""
        plan = QueryPlanner.parse("collagen -serum -mask")
        self.assertEqual(
            plan.global_negatives, {"serum", "mask"}
        )
        self.assertIsInstance(plan.ast, TermNode)

    def test_empty_query_raises(self) -> None:
        """A query with no search terms raises ValueError."""
        with self.assertRaises(ValueError):
            QueryPlanner.parse("-serum -mask")

    def test_unbalanced_paren_raises(self) -> None:
        """Unbalanced parentheses raise ValueError."""
        with self.assertRaises(ValueError):
            QueryPlanner.parse("(collagen OR peptides")


# ── DNF base queries ─────────────────────────────────────


class TestDNFExpansion(unittest.TestCase):
    """Verify DNF expansion produces correct base queries."""

    def test_simple_term(self) -> None:
        """Single term → one base query."""
        plan = QueryPlanner.parse("collagen")
        self.assertEqual(plan.base_queries, ["collagen"])

    def test_and_terms(self) -> None:
        """AND terms → single base query with both words."""
        plan = QueryPlanner.parse("collagen powder")
        self.assertEqual(plan.base_queries, ["collagen powder"])

    def test_or_terms(self) -> None:
        """OR terms → two separate base queries."""
        plan = QueryPlanner.parse("collagen OR peptides")
        self.assertEqual(
            sorted(plan.base_queries),
            ["collagen", "peptides"],
        )

    def test_distributive_expansion(self) -> None:
        """(A OR B) AND C → [A C, B C]."""
        plan = QueryPlanner.parse(
            "(collagen OR peptides) AND powder"
        )
        self.assertEqual(
            sorted(plan.base_queries),
            ["collagen powder", "peptides powder"],
        )

    def test_complex_expansion(self) -> None:
        """Full boolean expression expands correctly."""
        plan = QueryPlanner.parse(
            '("multi collagen" OR "types I II III") '
            "AND powder -serum"
        )
        self.assertEqual(
            sorted(plan.base_queries),
            [
                "multi collagen powder",
                "types I II III powder",
            ],
        )
        self.assertEqual(plan.global_negatives, {"serum"})

    def test_phrases_in_queries(self) -> None:
        """Phrases appear unquoted in base queries (plain text)."""
        plan = QueryPlanner.parse('"hyaluronic acid"')
        self.assertEqual(
            plan.base_queries, ["hyaluronic acid"]
        )


# ── Local evaluate ───────────────────────────────────────


class TestLocalEvaluate(unittest.TestCase):
    """Evaluate product titles against AST nodes."""

    def test_term_match(self) -> None:
        """TermNode matches case-insensitively."""
        node = TermNode("collagen")
        self.assertTrue(
            local_evaluate("Marine Collagen Powder", node)
        )

    def test_term_miss(self) -> None:
        """TermNode misses when substring absent."""
        node = TermNode("collagen")
        self.assertFalse(
            local_evaluate("Vitamin D Supplement", node)
        )

    def test_phrase_match(self) -> None:
        """PhraseNode matches exact phrase."""
        node = PhraseNode("multi collagen")
        self.assertTrue(
            local_evaluate(
                "Best Multi Collagen Peptides", node
            )
        )

    def test_phrase_miss_partial(self) -> None:
        """PhraseNode misses when words present but not as phrase."""
        node = PhraseNode("collagen powder")
        self.assertFalse(
            local_evaluate(
                "Collagen Peptides with Vitamin Powder", node
            )
        )

    def test_and_all_match(self) -> None:
        """AndNode requires all children to match."""
        node = AndNode(
            [TermNode("collagen"), TermNode("powder")]
        )
        self.assertTrue(
            local_evaluate("Collagen Powder Mix", node)
        )

    def test_and_partial_miss(self) -> None:
        """AndNode fails if any child misses."""
        node = AndNode(
            [TermNode("collagen"), TermNode("powder")]
        )
        self.assertFalse(
            local_evaluate("Collagen Serum", node)
        )

    def test_or_any_match(self) -> None:
        """OrNode succeeds if any child matches."""
        node = OrNode(
            [TermNode("collagen"), TermNode("vitamin")]
        )
        self.assertTrue(
            local_evaluate("Vitamin D Supplement", node)
        )

    def test_or_none_match(self) -> None:
        """OrNode fails if no child matches."""
        node = OrNode(
            [TermNode("collagen"), TermNode("vitamin")]
        )
        self.assertFalse(
            local_evaluate("Omega 3 Fish Oil", node)
        )

    def test_complex_nested(self) -> None:
        """Nested AND/OR evaluates correctly."""
        # (collagen OR peptides) AND powder
        node = AndNode(
            [
                OrNode(
                    [
                        TermNode("collagen"),
                        TermNode("peptides"),
                    ]
                ),
                TermNode("powder"),
            ]
        )
        self.assertTrue(
            local_evaluate("Collagen Powder", node)
        )
        self.assertTrue(
            local_evaluate("Peptides Powder Mix", node)
        )
        self.assertFalse(
            local_evaluate("Collagen Serum", node)
        )
        self.assertFalse(
            local_evaluate("Omega Powder", node)
        )


# ── Boolean syntax detection ─────────────────────────────


class TestBooleanDetection(unittest.TestCase):
    """Detect boolean syntax in raw queries."""

    def test_simple_query_no_boolean(self) -> None:
        """Plain words → no boolean syntax."""
        self.assertFalse(has_boolean_syntax("collagen"))

    def test_semicolon_no_boolean(self) -> None:
        """Semicolon multi-query → no boolean syntax."""
        self.assertFalse(
            has_boolean_syntax("collagen;vitamin")
        )

    def test_and_detected(self) -> None:
        """AND keyword triggers detection."""
        self.assertTrue(
            has_boolean_syntax("collagen AND powder")
        )

    def test_or_detected(self) -> None:
        """OR keyword triggers detection."""
        self.assertTrue(
            has_boolean_syntax("collagen OR peptides")
        )

    def test_parens_detected(self) -> None:
        """Parentheses trigger detection."""
        self.assertTrue(
            has_boolean_syntax("(collagen)")
        )

    def test_quotes_detected(self) -> None:
        """Double quotes trigger detection."""
        self.assertTrue(
            has_boolean_syntax('"multi collagen"')
        )

    def test_negation_only_no_boolean(self) -> None:
        """Bare negations without operators are not boolean."""
        self.assertFalse(
            has_boolean_syntax("collagen -serum")
        )

    def test_empty_string_no_boolean(self) -> None:
        """Empty string is not boolean."""
        self.assertFalse(has_boolean_syntax(""))

    def test_just_parens_is_boolean(self) -> None:
        """A lone parenthesis triggers boolean detection."""
        self.assertTrue(has_boolean_syntax("(collagen)"))

    def test_just_quotes_is_boolean(self) -> None:
        """A lone quoted phrase triggers boolean detection."""
        self.assertTrue(has_boolean_syntax('"collagen"'))

    def test_hyphenated_word_not_boolean(self) -> None:
        """Hyphenated normal words are not boolean."""
        self.assertFalse(
            has_boolean_syntax("anti-aging cream")
        )


# ── Extra tokenizer edge cases ───────────────────────────


class TestTokenizerEdgeCases(unittest.TestCase):
    """Additional tokenizer tests for edge inputs."""

    def test_empty_input(self) -> None:
        """Empty string produces no tokens."""
        tokens = tokenize("")
        self.assertEqual(len(tokens), 0)

    def test_only_negations(self) -> None:
        """Input with only negation tokens."""
        tokens = tokenize("-serum -cream")
        types = [t.type for t in tokens]
        self.assertEqual(
            types,
            [TokenType.NEGATION, TokenType.NEGATION],
        )
        self.assertEqual(tokens[0].value, "serum")
        self.assertEqual(tokens[1].value, "cream")

    def test_empty_quoted_phrase(self) -> None:
        """Empty quotes produce a PHRASE token with empty value."""
        tokens = tokenize('""')
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].type, TokenType.PHRASE)
        self.assertEqual(tokens[0].value, "")


# ── Extra parser edge cases ──────────────────────────────


class TestParserEdgeCases(unittest.TestCase):
    """Additional parsing edge cases."""

    def test_deeply_nested_parens(self) -> None:
        """Deeply nested parentheses parse correctly."""
        plan = QueryPlanner.parse("(((collagen)))")
        self.assertEqual(plan.base_queries, ["collagen"])

    def test_only_negations_raises(self) -> None:
        """A query with only negation tokens raises."""
        with self.assertRaises(ValueError):
            QueryPlanner.parse("-serum -cream")

    def test_local_evaluate_empty_title(self) -> None:
        """local_evaluate with empty title returns False for terms."""
        node = TermNode("collagen")
        self.assertFalse(local_evaluate("", node))

    def test_local_evaluate_empty_or_node(self) -> None:
        """OrNode with no children matches nothing — edge case."""
        node = OrNode(children=[])
        # any() on empty iterable returns False
        self.assertFalse(
            local_evaluate("anything", node)
        )

    def test_local_evaluate_empty_and_node(self) -> None:
        """AndNode with no children matches everything — edge case."""
        node = AndNode(children=[])
        # all() on empty iterable returns True
        self.assertTrue(
            local_evaluate("anything", node)
        )
