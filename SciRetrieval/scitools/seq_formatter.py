"""SeqFormatter tool — biological sequence operations.

Supports formatting, GC-content calculation, reverse complement,
and translation.  Uses Biopython when available for robust
handling; provides pure-Python fallbacks for common operations.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Biopython import
# ---------------------------------------------------------------------------
try:
    from Bio.Seq import Seq as BioSeq

    HAS_BIOPYTHON = True
except ImportError:
    HAS_BIOPYTHON = False
    BioSeq = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------
DNA_BASES = frozenset("ACTGactg")
RNA_BASES = frozenset("ACUGacug")
AMINO_ACIDS = frozenset(
    "ACDEFGHIKLMNPQRSTVWYacdefghiklmnpqrstvwy"
)

# Standard genetic code (DNA -> protein)
GENETIC_CODE: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

DNA_COMPLEMENT = str.maketrans("ACTGactg", "TGACtgac")


def _validate_sequence(seq: str) -> str | None:
    """Validate the sequence and return its type or an error message.

    Returns:
        ``"dna"``, ``"rna"``, or ``"protein"`` if valid, or an error
        string if invalid characters are found.
    """
    if not seq:
        return "Sequence is empty"

    chars = set(seq)
    if chars.issubset(DNA_BASES):
        return "dna"
    if chars.issubset(RNA_BASES):
        return "rna"
    if chars.issubset(AMINO_ACIDS):
        return "protein"
    # Allow whitespace and common punctuation
    allowed_extras = set(" \n\r\t-*")
    remaining = chars - DNA_BASES - RNA_BASES - AMINO_ACIDS - allowed_extras
    if remaining:
        invalid = "".join(sorted(remaining))
        return f"Invalid sequence characters: {invalid!r}"
    # Mixed — try to guess
    if chars & DNA_BASES and not (chars - DNA_BASES - allowed_extras):
        return "dna"
    if chars & RNA_BASES and not (chars - RNA_BASES - allowed_extras):
        return "rna"
    return "protein"


def _format_sequence(seq: str, width: int = 60) -> str:
    """Wrap sequence at *width* characters."""
    cleaned = seq.replace(" ", "").replace("\n", "").replace("\r", "")
    return "\n".join(cleaned[i : i + width] for i in range(0, len(cleaned), width))


def _gc_content(seq: str) -> float:
    """Calculate GC content as a percentage (0-100)."""
    cleaned = seq.upper().replace(" ", "").replace("\n", "").replace("\r", "")
    if not cleaned:
        return 0.0
    gc_count = cleaned.count("G") + cleaned.count("C")
    return (gc_count / len(cleaned)) * 100.0


def _reverse_complement(seq: str) -> str:
    """Compute the reverse complement of a DNA sequence."""
    cleaned = seq.upper().replace(" ", "").replace("\n", "").replace("\r", "")
    return cleaned.translate(DNA_COMPLEMENT)[::-1]


def _translate_dna(seq: str) -> str:
    """Translate a DNA coding sequence to protein (standard code).

    Finds the first start codon (ATG) and translates until a stop codon
    or the end of the sequence.
    """
    cleaned = seq.upper().replace(" ", "").replace("\n", "").replace("\r", "")

    # Find first start codon
    start = cleaned.find("ATG")
    if start == -1:
        # No start codon — translate from the beginning
        start = 0

    protein: list[str] = []
    for i in range(start, len(cleaned) - 2, 3):
        codon = cleaned[i : i + 3]
        if len(codon) < 3:
            break
        aa = GENETIC_CODE.get(codon, "X")
        protein.append(aa)
        if aa == "*":
            break

    return "".join(protein)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


class SeqFormatter(ITool):
    """Performs operations on biological sequences.

    Supports formatting (wrapping), GC-content calculation, reverse
    complement, and translation.  Biopython is optional — pure-Python
    fallbacks work for standard cases.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="format_sequence",
            description=(
                "Perform operations on a biological sequence. "
                "Supports: 'format' (wrap at 60 chars), "
                "'gc_content' (calculate GC percentage), "
                "'reverse_complement' (DNA complement), "
                "'translate' (DNA to protein)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sequence": {
                        "type": "string",
                        "description": (
                            "The biological sequence (DNA, RNA, or protein)."
                        ),
                    },
                    "operation": {
                        "type": "string",
                        "description": (
                            "Operation to perform: 'format', 'gc_content', "
                            "'reverse_complement', or 'translate'."
                        ),
                        "default": "format",
                        "enum": [
                            "format",
                            "gc_content",
                            "reverse_complement",
                            "translate",
                        ],
                    },
                    "output_format": {
                        "type": "string",
                        "description": (
                            "Output format (currently only 'fasta' is "
                            "supported for the 'format' operation)."
                        ),
                        "default": "fasta",
                    },
                },
                "required": ["sequence"],
            },
            category=ToolCategory.BIOLOGY,
        )

    async def run(
        self, context: ToolContext, **kwargs: object
    ) -> ToolResult:
        """Execute the sequence operation.

        Args:
            context: Execution context with logger.
            **kwargs: Must contain ``sequence`` (str).  Optional:
                ``operation`` (str, default ``"format"``),
                ``output_format`` (str, default ``"fasta"``).

        Returns:
            :class:`ToolResult` with the operation result.
        """
        sequence = kwargs.get("sequence")
        if not sequence:
            return ToolResult(
                success=False,
                content="",
                error="Missing required argument: 'sequence'",
            )

        seq_str = str(sequence).strip()
        if not seq_str:
            return ToolResult(
                success=False, content="", error="Sequence is empty"
            )

        operation = str(kwargs.get("operation", "format"))
        output_format = str(kwargs.get("output_format", "fasta"))

        # Validate sequence
        validation = _validate_sequence(seq_str)
        if validation is None or isinstance(validation, str) and validation in (
            "dna",
            "rna",
            "protein",
        ):
            seq_type: str = validation if validation else "dna"  # type: ignore[assignment]
        else:
            return ToolResult(
                success=False, content="", error=validation
            )

        try:
            result = self._execute_operation(
                seq_str, seq_type, operation, output_format
            )
            return ToolResult(
                success=True,
                content=result,
                metadata={
                    "operation": operation,
                    "sequence_type": seq_type,
                    "length": len(seq_str.replace(" ", "").replace("\n", "")),
                },
            )
        except Exception as exc:
            context.logger.warning("seq_formatter failed: %s", exc)
            return ToolResult(
                success=False,
                content="",
                error=f"Sequence operation failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_operation(
        seq: str, seq_type: str, operation: str, output_format: str
    ) -> str:
        """Run the requested operation and return the formatted output."""
        if HAS_BIOPYTHON:
            bio_seq = BioSeq(seq)

        if operation == "format":
            wrapped = _format_sequence(seq, width=60)
            if output_format == "fasta":
                # Simple fasta-like output (no header)
                return wrapped
            return wrapped

        elif operation == "gc_content":
            pct = _gc_content(seq)
            return f"GC content: {pct:.2f}%"

        elif operation == "reverse_complement":
            if seq_type not in ("dna", "rna"):
                raise ValueError(
                    f"Reverse complement is only defined for DNA/RNA, "
                    f"got {seq_type}"
                )
            if HAS_BIOPYTHON:
                result = str(bio_seq.reverse_complement())
            else:
                result = _reverse_complement(seq)

            # Wrap if longer than 60
            if len(result) > 60:
                result = _format_sequence(result, width=60)
            return result

        elif operation == "translate":
            if seq_type != "dna":
                raise ValueError(
                    f"Translation requires DNA sequence, got {seq_type}"
                )
            if HAS_BIOPYTHON:
                result = str(bio_seq.translate())
            else:
                result = _translate_dna(seq)
            return result

        else:
            raise ValueError(f"Unknown operation: {operation!r}")
