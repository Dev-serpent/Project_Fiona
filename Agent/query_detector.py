"""Lightweight heuristic-based query-vs-task classifier.

Zero LLM calls — uses regex patterns and simple heuristics to
distinguish conversational queries (greetings, simple questions)
from actionable tasks that warrant multi-agent orchestration.

Usage::

    >>> from Agent.query_detector import QueryDetector, QueryOrTask
    >>> QueryDetector.classify("hello")
    <QueryOrTask.QUERY: 'query'>
    >>> QueryDetector.classify("make a module that fetches data from an API")
    <QueryOrTask.TASK: 'task'>
"""

from __future__ import annotations

import enum
import re
from typing import Final


class QueryOrTask(enum.Enum):
    """Classification result from :meth:`QueryDetector.classify`."""

    QUERY = "query"
    TASK = "task"


# ---------------------------------------------------------------------------
# Heuristic patterns — deliberately conservative
# ---------------------------------------------------------------------------

# Greetings and social openings
_GREETINGS: Final[re.Pattern[str]] = re.compile(
    r"^(hi|hello|hey|yo|sup|howdy|greetings|good\s*morning"
    r"|good\s*evening|good\s*afternoon|what'?s\s*up"
    r"|how'?s\s*it\s*going|nice\s*to\s*meet\s*you"
    r"|pleased?\s*to\s*meet\s*you)[\s.!?]*$",
    re.IGNORECASE,
)

# Simple question starters — these almost never need orchestration
_QUESTION_STARTERS: Final[re.Pattern[str]] = re.compile(
    r"^(what|who|when|where|why|how|is|are|was|were"
    r"|do|does|did|can|could|will|would|shall|should"
    r"|may|might|has|have|had|doesn'?t|don'?t|isn'?t"
    r"|aren'?t|wasn'?t|weren'?t)\s",
    re.IGNORECASE,
)

# Reflexive / chit-chat phrases
_CHITCHAT: Final[re.Pattern[str]] = re.compile(
    r"^(i\s+(am|'m)\s+(fine|good|great|ok|okay|doing\s*well)"
    r"|how\s+(are|about|do|does)"
    r"|tell\s+me\s+(about|yourself)"
    r"|who\s+(are|made|created)\s+you"
    r"|what\s+(can|do)\s+you\s+(do|help)"
    r"|thank(s| you)|thanks|you'?re?\s+welcome"
    r"|bye|goodbye|see\s+you|talk\s+(to\s+you\s+)?later"
    r"|no\s+(problem|worries|thank\s*you)"
    r"|sure|okay|ok|alright|got\s+it|understood"
    r"|that'?s?\s+(great|awesome|cool|nice|perfect|fine)"
    r"|i\s+(agree|understand|see|know)"
    r"|makes?\s+sense"
    r"|(can|could)\s+you\s+(repeat|clarify|elaborate|explain)\b)"
    r".*$",
    re.IGNORECASE,
)

# Imperative action verbs — strong signal for a task
_ACTION_VERBS: Final[re.Pattern[str]] = re.compile(
    r"\b("
    r"make|create|build|construct|implement|write|code|program"
    r"|develop|configure|setup|set\s*up|install|deploy|migrate"
    r"|convert|translate|transform|refactor|restructure|redesign"
    r"|rewrite|rebuild|rework"
    r"|fix|repair|debug|patch|resolve|troubleshoot"
    r"|test|audit|review|inspect|check|validate|verify"
    r"|open|launch|run|start|stop|close|kill|exit|quit"
    r"|show|display|hide|focus|switch|select|highlight"
    r"|press|click|type|enter|key|keystroke"
    r"|move|scroll|drag|drop|resize|minimize|maximize|restore"
    r"|copy|paste|cut|undo|redo|save|discard"
    r"|add|insert|append|extend|augment|enhance|improve"
    r"|change|modify|update|upgrade|edit"
    r"|remove|delete|strip|drop|prune|clean|clear"
    r"|integrate|connect|link|bridge|join|combine|merge"
    r"|automate|schedule|trigger|hook|wire"
    r"|research|investigate|explore|analyze|analyse"
    r"|document|explain|describe|summarize|summarise"
    r"|generate|produce|render|compile|assemble"
    r"|register|subscribe|publish|broadcast|notify"
    r"|import|export|load|save|store|backup|restore"
    r"|optimize|optimise|tune|benchmark|profile"
    r"|authenticate|authorize|encrypt|decrypt|hash"
    r"|monitor|watch|track|observe|log|report"
    r")\b",
    re.IGNORECASE,
)

# Technical / code references — strong task signal
_TECH_REFERENCES: Final[re.Pattern[str]] = re.compile(
    r"\b("
    r"module|package|library|dependency|plugin|extension"
    r"|function|method|class|object|struct|interface|protocol"
    r"|api|endpoint|route|middleware|handler|controller"
    r"|database|schema|table|query|index|migration"
    r"|config|configuration|setting|environment|variable"
    r"|script|program|binary|executable|daemon|service"
    r"|thread|process|worker|pool|queue"
    r"|file|directory|folder|path|repo|repository"
    r"|test|spec|suite|assertion|coverage"
    r"|deploy|pipeline|ci|cd|workflow"
    r"|server|client|socket|port|protocol"
    r"|compiler|interpreter|transpiler|bundler|linter"
    r"|\.py\b|\.js\b|\.ts\b|\.java\b|\.rs\b|\.go\b|\.c\b|\.cpp\b|\.h\b"
    r"|\.json\b|\.yaml\b|\.toml\b|\.xml\b|\.csv\b"
    r")",
    re.IGNORECASE,
)

# Very short messages that are not greetings or questions → still a query
_SHORT_QUERY_THRESHOLD: Final[int] = 15

# Messages longer than this are probably tasks
_LONG_MESSAGE_THRESHOLD: Final[int] = 300


class QueryDetector:
    """Stateless heuristic classifier for query-vs-task decisions.

    All patterns are compiled once at module load.  Classification
    adds zero measurable latency (microseconds, no I/O).
    """

    @staticmethod
    def classify(message: str) -> QueryOrTask:
        """Return ``QUERY`` or ``TASK`` based on heuristic rules.

        Rules are applied in order; the first match wins:

        1. Empty/whitespace → QUERY (conservative default)
        2. Greeting pattern → QUERY
        3. Chit-chat pattern → QUERY
        4. Question starter → QUERY
        5. Very long message → TASK (likely detailed request)
        6. Action verb present → TASK
        7. Technical reference present → TASK
        8. Single code-like token → TASK
        9. Short message → QUERY (anything not matched is treated as query)
        """
        stripped = message.strip()
        if not stripped:
            return QueryOrTask.QUERY

        # 2 — Greetings (pure social, never a task)
        if _GREETINGS.match(stripped):
            return QueryOrTask.QUERY

        # 3 — Chit-chat (social phrases, never a task)
        if _CHITCHAT.match(stripped):
            return QueryOrTask.QUERY

        # 4 — Very long message → likely a detailed task description
        if len(stripped) > _LONG_MESSAGE_THRESHOLD:
            return QueryOrTask.TASK

        # 5 — Action verb present (strongest task signal).
        #     Check BEFORE question starters so that "Can you implement
        #     an API?" is correctly classified as TASK despite being
        #     framed as a question.
        if _ACTION_VERBS.search(stripped):
            return QueryOrTask.TASK

        # 6 — Simple question (no action verbs → pure query).
        #     Check BEFORE tech references so that "Where is the config
        #     file?" is treated as QUERY despite containing tech terms.
        if _QUESTION_STARTERS.match(stripped):
            return QueryOrTask.QUERY

        # 7 — Technical reference present (task signal)
        if _TECH_REFERENCES.search(stripped):
            return QueryOrTask.TASK

        # 8 — Short enough that it's probably a simple query
        if len(stripped) < _SHORT_QUERY_THRESHOLD:
            return QueryOrTask.QUERY

        # 9 — Default: conservatively treat as query
        return QueryOrTask.QUERY
