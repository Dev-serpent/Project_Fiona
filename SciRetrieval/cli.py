"""SciRetrieval CLI — registered as 'fiona sire <command>' in fiona/cli.py."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from SciRetrieval import (
    Router,
    ProviderRegistry,
    Normalizer,
    EntityResolver,
    RetrievalManager,
    CacheManager,
)
from SciRetrieval.scilab.engine import SciLabEngine
from SciRetrieval.cache.cache_backend import MemoryBackend, DiskBackend
from SciRetrieval.providers.ncbi import NCBIProvider
from SciRetrieval.providers.pubchem import PubChemProvider
from SciRetrieval.providers.nist import NISTProvider
from SciRetrieval.scilab.parser import SciLabParser
from SciRetrieval.scilab.ranker import Ranker
from SciRetrieval.scilab.deduplicator import Deduplicator
from SciRetrieval.scilab.summarizer import Summarizer
from SciRetrieval.scilab.context_generator import ContextGenerator
from SciRetrieval.maintext_bridge import MainTextBridge
from SciRetrieval.errors import SciRetrievalError


def _build_manager():
    """Build a fully wired RetrievalManager for CLI use."""
    # Router
    keyword_path = Path(__file__).parent / "data" / "keywordlist.json"
    router = Router(keyword_path)

    # Providers
    ncbi = NCBIProvider()
    pubchem = PubChemProvider()
    nist = NISTProvider()

    # Registry
    from SciPhi.interfaces.model import ScientificDomain

    registry = ProviderRegistry()
    registry.register(pubchem, [ScientificDomain.CHEMISTRY], primary=True)
    registry.register(ncbi, [ScientificDomain.BIOLOGY], primary=True)
    registry.register(
        nist,
        [ScientificDomain.CHEMISTRY, ScientificDomain.PHYSICS, ScientificDomain.ENGINEERING],
        primary=False,
    )
    registry.register(pubchem, [ScientificDomain.BIOLOGY], primary=False)

    # Normalizer
    normalizer = Normalizer()
    from SciRetrieval.normalizer import _normalize_pubchem, _normalize_ncbi, _normalize_nist

    normalizer.register_adapter("pubchem", _normalize_pubchem)
    normalizer.register_adapter("ncbi", _normalize_ncbi)
    normalizer.register_adapter("nist", _normalize_nist)

    # Entity Resolver
    synonym_path = Path(__file__).parent / "data" / "synonyms.json"
    resolver = EntityResolver(synonym_path if synonym_path.exists() else None)

    # SciLab
    parser = SciLabParser()
    ranker = Ranker()
    dedup = Deduplicator()
    summarizer = Summarizer()
    context_gen = ContextGenerator()
    scilab = SciLabEngine(parser, ranker, dedup, summarizer, context_gen)

    # Cache
    mem_backend = MemoryBackend()
    disk_cache_dir = Path(__file__).parent / "data" / "cache"
    nist_cache_dir = Path(__file__).parent / "data" / "nist_cache"
    disk_backend = DiskBackend(disk_cache_dir)
    nist_disk_backend = DiskBackend(nist_cache_dir)
    cache_mgr = CacheManager(
        conversation_backend=mem_backend,
        dataset_backend=disk_backend,
        persistent_backend=nist_disk_backend,
    )

    # Retrieval Manager
    manager = RetrievalManager(
        classifier=router,
        registry=registry,
        normalizer=normalizer,
        resolver=resolver,
        scilab=scilab,
        cache_manager=cache_mgr,
    )
    return manager


def build_parser() -> argparse.ArgumentParser:
    """Build the SciRetrieval argument parser."""
    parser = argparse.ArgumentParser(
        prog="fiona sire",
        description="Scientific knowledge retrieval from NCBI, PubChem, NIST.",
    )
    sub = parser.add_subparsers(dest="sire_command", required=True)

    # fiona sire query <text>
    query_p = sub.add_parser("query", help="Run a full scientific retrieval query.")
    query_p.add_argument("query_text", nargs="+", help="The scientific question")

    # fiona sire getdata <provider> <entity>
    getdata_p = sub.add_parser("getdata", help="Direct provider lookup (GetData).")
    getdata_p.add_argument("provider", choices=["pubchem", "ncbi", "nist"])
    getdata_p.add_argument("entity", help="Entity ID or name")
    getdata_p.add_argument("--fields", nargs="*", default=[], help="Fields to retrieve")

    # fiona sire classify <text>
    classify_p = sub.add_parser(
        "classify", help="Classify query domain/intent only (no retrieval)."
    )
    classify_p.add_argument("query_text", nargs="+")

    # fiona sire cache clear
    cache_p = sub.add_parser("cache", help="Manage caches.")
    cache_sub = cache_p.add_subparsers(dest="cache_command")
    cache_sub.add_parser("clear", help="Clear all caches")
    cache_sub.add_parser("evict", help="Evict expired entries")

    # fiona sire providers
    sub.add_parser("providers", help="List registered providers")

    # fiona sire resolve <text>
    resolve_p = sub.add_parser(
        "resolve", help="Show how EntityResolver would resolve a query."
    )
    resolve_p.add_argument("query_text", nargs="+")

    return parser


def run(raw_args: list[str]) -> None:
    """Entry point for 'fiona sire'."""
    parser = build_parser()
    args = parser.parse_args(raw_args)

    if args.sire_command == "classify":
        query = " ".join(args.query_text)
        keyword_path = Path(__file__).parent / "data" / "keywordlist.json"
        router = Router(keyword_path)
        result = asyncio.run(router.classify(query))
        print(f"Query: {query}")
        print(f"Primary Domain: {result.primary_domain.name}")
        print(
            f"Secondary Domain: {result.secondary_domain.name if result.secondary_domain else 'None'}"
        )
        print(f"Intent: {result.intent}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Matched Keywords: {result.matched_keywords}")
        return

    if args.sire_command == "providers":
        manager = _build_manager()
        registry = manager._registry
        info = registry.list_providers()
        print("Registered Providers:")
        for name, domains in info.items():
            print(f"  {name}: {', '.join(domains)}")
        return

    if args.sire_command == "query":
        query = " ".join(args.query_text)
        manager = _build_manager()
        bridge = MainTextBridge(manager)
        result = asyncio.run(bridge.on_scientific_query(query))
        print(result)
        return

    if args.sire_command == "getdata":
        query = " ".join(args.query_text) if hasattr(args, "query_text") else ""
        entity = args.entity
        provider = args.provider
        manager = _build_manager()
        bridge = MainTextBridge(manager)
        options = {"fields": args.fields} if args.fields else {}
        result = asyncio.run(bridge.on_get_data(provider, entity, options))
        print(result)
        return

    if args.sire_command == "cache":
        manager = _build_manager()
        if args.cache_command == "clear":
            asyncio.run(manager.cache_manager.evict_expired_all())
            print("All caches cleared.")
        elif args.cache_command == "evict":
            counts = asyncio.run(manager.cache_manager.evict_expired_all())
            print(
                f"Evicted: conversation={counts['conversation']}, "
                f"dataset={counts['dataset']}, persistent={counts['persistent']}"
            )
        return

    if args.sire_command == "resolve":
        query = " ".join(args.query_text)
        synonym_path = Path(__file__).parent / "data" / "synonyms.json"
        resolver = EntityResolver(synonym_path if synonym_path.exists() else None)

        key = query.lower().strip()
        if resolver._synonym_registry:
            entry = resolver._synonym_registry.get(key)
            if entry:
                print(f"Resolved '{query}' \u2192")
                print(f"  Canonical Name: {entry.canonical_name}")
                print(f"  Canonical ID: {entry.canonical_id}")
                print(f"  Aliases: {', '.join(entry.aliases)}")
                print(f"  Type: {entry.entity_type}")
            else:
                print(f"'{query}' not found in synonym registry")
        else:
            print(f"No synonym registry loaded (synonyms.json not found)")


if __name__ == "__main__":
    run(sys.argv[1:])
