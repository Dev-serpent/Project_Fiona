"""Tests for the SciRetrieval CLI argument parsing.

Tests argument parsing independent of the actual pipeline execution.
"""

from __future__ import annotations

from SciRetrieval.cli import build_parser


class TestCLIQuerySubcommand:
    """'fiona sire query <text>' parsing."""

    def test_query_with_single_word(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["query", "aspirin"])
        assert args.sire_command == "query"
        assert args.query_text == ["aspirin"]

    def test_query_with_multi_word(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["query", "what", "is", "aspirin"])
        assert args.sire_command == "query"
        assert args.query_text == ["what", "is", "aspirin"]

    def test_query_requires_argument(self) -> None:
        parser = build_parser()
        # Should raise SystemExit because query_text is required (nargs=+)
        import sys
        try:
            parser.parse_args(["query"])
            assert False, "Should have raised SystemExit"
        except SystemExit:
            pass


class TestCLIClassifySubcommand:
    """'fiona sire classify <text>' parsing."""

    def test_classify_with_text(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["classify", "gene", "mutation"])
        assert args.sire_command == "classify"
        assert args.query_text == ["gene", "mutation"]

    def test_classify_requires_argument(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["classify"])
            assert False, "Should have raised SystemExit"
        except SystemExit:
            pass


class TestCLIGetDataSubcommand:
    """'fiona sire getdata <provider> <entity>' parsing."""

    def test_getdata_with_provider_and_entity(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["getdata", "pubchem", "aspirin"])
        assert args.sire_command == "getdata"
        assert args.provider == "pubchem"
        assert args.entity == "aspirin"

    def test_getdata_with_fields(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["getdata", "ncbi", "TP53", "--fields", "summary", "organism"]
        )
        assert args.fields == ["summary", "organism"]

    def test_getdata_provider_choices(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["getdata", "invalid_provider", "test"])
            assert False, "Should have raised SystemExit for invalid choice"
        except SystemExit:
            pass

    def test_getdata_requires_entity(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["getdata", "pubchem"])
            assert False, "Should have raised SystemExit"
        except SystemExit:
            pass


class TestCLIProvidersSubcommand:
    """'fiona sire providers' parsing."""

    def test_providers_no_args(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["providers"])
        assert args.sire_command == "providers"

    def test_providers_with_extra_args_fails(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["providers", "extra"])
            assert False
        except SystemExit:
            pass


class TestCLIResolveSubcommand:
    """'fiona sire resolve <text>' parsing."""

    def test_resolve_with_text(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["resolve", "aspirin"])
        assert args.sire_command == "resolve"
        assert args.query_text == ["aspirin"]

    def test_resolve_multi_word(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["resolve", "tumor", "protein", "p53"])
        assert args.query_text == ["tumor", "protein", "p53"]

    def test_resolve_requires_argument(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["resolve"])
            assert False
        except SystemExit:
            pass


class TestCLICacheSubcommand:
    """'fiona sire cache <subcommand>' parsing."""

    def test_cache_clear(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cache", "clear"])
        assert args.sire_command == "cache"
        assert args.cache_command == "clear"

    def test_cache_evict(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["cache", "evict"])
        assert args.sire_command == "cache"
        assert args.cache_command == "evict"

    def test_cache_no_subcommand_defaults(self) -> None:
        """cache subcommand without sub-subcommand is valid, cache_command is None."""
        parser = build_parser()
        args = parser.parse_args(["cache"])
        assert args.sire_command == "cache"
        assert args.cache_command is None  # not required by default

    def test_cache_unknown_subcommand_fails(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["cache", "unknown"])
            assert False
        except SystemExit:
            pass


class TestCLIHelp:
    """Help and error cases."""

    def test_no_args_fails(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args([])
            assert False
        except SystemExit:
            pass

    def test_unknown_command_fails(self) -> None:
        parser = build_parser()
        import sys
        try:
            parser.parse_args(["unknown_command"])
            assert False
        except SystemExit:
            pass
