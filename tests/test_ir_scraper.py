"""Tests for IR scraper link discovery logic."""

from legacy_retrieval.ingestion.ir_scraper import IrScraper


def test_domain_allowed():
    assert IrScraper._domain_allowed("investor.nvidia.com", ["nvidia.com"])
    assert IrScraper._domain_allowed("www.microsoft.com", ["microsoft.com"])
    assert not IrScraper._domain_allowed("evil.com", ["nvidia.com"])


def test_matches_patterns():
    patterns = ["earnings", ".pdf", "presentation"]
    assert IrScraper._matches_patterns("https://x.com/earnings-q1.pdf", patterns)
    assert IrScraper._matches_patterns("https://x.com/investor-presentation", patterns)
    assert not IrScraper._matches_patterns("https://x.com/careers", patterns)


def test_ir_configs_load():
    from legacy_retrieval.ingestion.ir_scraper import load_ir_configs

    configs = load_ir_configs()
    assert "MSFT" in configs
    assert "NVDA" in configs
    assert configs["MSFT"].base_url.startswith("https://")
