# src/filters/query_parser.py

"""Boolean query compiler with DNF expansion and local AST evaluation.

Parses user queries containing AND, OR, quoted phrases, and
negation prefixes into an Abstract Syntax Tree, converts to
Disjunctive Normal Form for parallel scraper dispatch, and
provides local evaluation against product titles.

Grammar (operator precedence: OR < AND < unary):
    expr     → and_expr (OR and_expr)*
    and_expr → unary (AND? unary)*
    unary    → PHRASE | WORD | LPAREN expr RPAREN
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("ecom_search.query_parser")


# ── Token types ──────────────────────────────────────────


class TokenType(Enum):
    """Lexical token types for the query language."""

    PHRASE = auto()
    WORD = auto()
    AND = auto()
    OR = auto()
    LPAREN = auto()
    RPAREN = auto()
    NEGATION = auto()


@dataclass
class Token:
    """A single lexical token."""

    type: TokenType
    value: str


# ── AST node types ───────────────────────────────────────


@dataclass
class TermNode:
    """A single unquoted search term."""

    value: str


@dataclass
class PhraseNode:
    """A quoted multi-word search phrase."""

    value: str


@dataclass
class AndNode:
    """Conjunction: all children must match."""

    children: list["ASTNode"]


@dataclass
class OrNode:
    """Disjunction: at least one child must match."""

    children: list["ASTNode"]


ASTNode = TermNode | PhraseNode | AndNode | OrNode


# ── Query plan dataclass ─────────────────────────────────


@dataclass
class QueryPlan:
    """Result of parsing a boolean query string."""

    ast: ASTNode
    base_queries: list[str]
    global_negatives: set[str] = field(
        default_factory=lambda: set[str]()
    )


# ── Tokenizer ────────────────────────────────────────────

# Matches: quoted strings, parentheses, or word tokens
_TOKEN_RE = re.compile(
    r"""
    "([^"]*)"       |   # 1: quoted phrase
    (\()            |   # 2: left paren
    (\))            |   # 3: right paren
    (-\w[\w]*)      |   # 4: negation  -keyword
    ([^\s()"]+)         # 5: bare word / AND / OR
    """,
    re.VERBOSE,
)


def tokenize(raw: str) -> list[Token]:
    """Split a raw query string into a list of tokens."""
    tokens: list[Token] = []
    for match in _TOKEN_RE.finditer(raw):
        phrase, lparen, rparen, negation, word = (
            match.group(1),
            match.group(2),
            match.group(3),
            match.group(4),
            match.group(5),
        )
        if phrase is not None:
            tokens.append(Token(TokenType.PHRASE, phrase))
        elif lparen:
            tokens.append(Token(TokenType.LPAREN, "("))
        elif rparen:
            tokens.append(Token(TokenType.RPAREN, ")"))
        elif negation:
            # Strip the leading '-'
            tokens.append(
                Token(TokenType.NEGATION, negation[1:])
            )
        elif word:
            upper = word.upper()
            if upper == "AND":
                tokens.append(Token(TokenType.AND, "AND"))
            elif upper == "OR":
                tokens.append(Token(TokenType.OR, "OR"))
            else:
                tokens.append(Token(TokenType.WORD, word))
    return tokens


# ── Recursive-descent parser ─────────────────────────────


class _Parser:
    """Recursive-descent parser for boolean search queries."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token | None:
        """Return the current token without consuming it."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> Token:
        """Consume and return the current token."""
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        """Consume a token of the expected type, or raise."""
        tok = self._peek()
        if tok is None or tok.type != tt:
            found = tok.value if tok else "end-of-input"
            msg = f"Expected {tt.name}, found '{found}'"
            raise ValueError(msg)
        return self._consume()

    def parse_expr(self) -> ASTNode:
        """Parse: expr → and_expr (OR and_expr)*."""
        left = self._parse_and_expr()
        children: list[ASTNode] = [left]
        while (
            self._peek() is not None
            and self._peek_is(TokenType.OR)
        ):
            self._consume()  # eat OR
            children.append(self._parse_and_expr())
        if len(children) == 1:
            return children[0]
        return OrNode(children=children)

    def _parse_and_expr(self) -> ASTNode:
        """Parse: and_expr → unary (AND? unary)*."""
        left = self._parse_unary()
        children: list[ASTNode] = [left]
        while self._peek() is not None:
            # Explicit AND
            if self._peek_is(TokenType.AND):
                self._consume()
                children.append(self._parse_unary())
            # Implicit AND: next token is a term/phrase/lparen
            elif self._peek_is_unary_start():
                children.append(self._parse_unary())
            else:
                break
        if len(children) == 1:
            return children[0]
        return AndNode(children=children)

    def _parse_unary(self) -> ASTNode:
        """Parse: unary → PHRASE | WORD | LPAREN expr RPAREN."""
        tok = self._peek()
        if tok is None:
            msg = "Unexpected end of query"
            raise ValueError(msg)
        if tok.type == TokenType.PHRASE:
            self._consume()
            return PhraseNode(value=tok.value)
        if tok.type == TokenType.WORD:
            self._consume()
            return TermNode(value=tok.value)
        if tok.type == TokenType.LPAREN:
            self._consume()
            node = self.parse_expr()
            self._expect(TokenType.RPAREN)
            return node
        msg = f"Unexpected token: '{tok.value}'"
        raise ValueError(msg)

    def _peek_is(self, tt: TokenType) -> bool:
        """Check whether the current token is of a given type."""
        tok = self._peek()
        return tok is not None and tok.type == tt

    def _peek_is_unary_start(self) -> bool:
        """Check whether the current token can start a unary."""
        tok = self._peek()
        return tok is not None and tok.type in {
            TokenType.WORD,
            TokenType.PHRASE,
            TokenType.LPAREN,
        }

    def is_exhausted(self) -> bool:
        """Return True when all tokens have been consumed."""
        return self._peek() is None


# ── DNF conversion ───────────────────────────────────────

# A conjunction is a flat list of leaf nodes (terms / phrases).
Conjunction = list[TermNode | PhraseNode]


def _to_dnf(node: ASTNode) -> list[Conjunction]:
    """Convert an AST to Disjunctive Normal Form.

    Returns a list of conjunctions (OR of ANDs).
    Each conjunction is a list of leaf nodes whose string
    representations are joined with spaces to form a base query.
    """
    if isinstance(node, (TermNode, PhraseNode)):
        return [[node]]

    if isinstance(node, OrNode):
        result: list[Conjunction] = []
        for child in node.children:
            result.extend(_to_dnf(child))
        return result

    # AndNode: distribute across children.
    # Product of all children's DNF lists.
    child_dnfs = [_to_dnf(c) for c in node.children]
    product: list[Conjunction] = [[]]
    for child_dnf in child_dnfs:
        new_product: list[Conjunction] = []
        for existing in product:
            for conj in child_dnf:
                new_product.append(existing + conj)
        product = new_product
    return product


def _conjunction_to_query(conjunction: Conjunction) -> str:
    """Convert a single conjunction (list of leaves) into a query string."""
    parts: list[str] = []
    for leaf in conjunction:
        if isinstance(leaf, PhraseNode):
            parts.append(leaf.value)
        else:
            parts.append(leaf.value)
    return " ".join(parts)


# ── Local evaluator ──────────────────────────────────────


def local_evaluate(text: str, node: ASTNode) -> bool:
    """Evaluate whether *text* satisfies the boolean AST.

    - ``TermNode``: case-insensitive substring check.
    - ``PhraseNode``: case-insensitive exact phrase check.
    - ``AndNode``: all children must match.
    - ``OrNode``: at least one child must match.
    """
    lowered = text.lower()

    if isinstance(node, TermNode):
        return node.value.lower() in lowered

    if isinstance(node, PhraseNode):
        return node.value.lower() in lowered

    if isinstance(node, AndNode):
        return all(
            local_evaluate(text, c) for c in node.children
        )

    # OrNode
    return any(
        local_evaluate(text, c) for c in node.children
    )


# ── Boolean syntax detection ─────────────────────────────

_BOOLEAN_PATTERN = re.compile(
    r"""
    \bAND\b   |
    \bOR\b    |
    [(")]
    """,
    re.VERBOSE | re.IGNORECASE,
)


def has_boolean_syntax(raw_query: str) -> bool:
    """Detect whether a raw query uses boolean operators or phrases."""
    return bool(_BOOLEAN_PATTERN.search(raw_query))


# ── Public API ───────────────────────────────────────────


class QueryPlanner:
    """Compile a human-written boolean query into a structured plan."""

    @staticmethod
    def parse(raw_query: str) -> QueryPlan:
        """Parse a raw query into an AST, base queries, and negatives.

        1. Extract trailing ``-keyword`` tokens as global negatives.
        2. Parse the remaining expression into an AST.
        3. Convert the AST to DNF to produce flat base query strings.
        """
        tokens = tokenize(raw_query)

        # Separate negation tokens from the expression tokens
        negatives: set[str] = set()
        expr_tokens: list[Token] = []
        for tok in tokens:
            if tok.type == TokenType.NEGATION:
                negatives.add(tok.value)
            else:
                expr_tokens.append(tok)

        if not expr_tokens:
            # Query contains only negations — nothing to search
            msg = "Query contains no search terms"
            raise ValueError(msg)

        parser = _Parser(expr_tokens)
        ast = parser.parse_expr()

        # Remaining unconsumed tokens mean a syntax error
        if not parser.is_exhausted():
            msg = "Unexpected token after expression"
            raise ValueError(msg)

        # Convert AST to DNF for scraper dispatch
        dnf = _to_dnf(ast)
        base_queries = [
            _conjunction_to_query(conj) for conj in dnf
        ]

        logger.info(
            "Parsed '%s' → %d base queries, "
            "%d global negatives",
            raw_query,
            len(base_queries),
            len(negatives),
        )

        return QueryPlan(
            ast=ast,
            base_queries=base_queries,
            global_negatives=negatives,
        )
