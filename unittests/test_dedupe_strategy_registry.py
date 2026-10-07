"""Tests for the deduplication Strategy registry in dojo.finding.deduplication."""

from django.conf import settings
from django.test import SimpleTestCase

from dojo.finding import deduplication


class TestDeduplicationStrategyRegistry(SimpleTestCase):

    def test_every_configured_algorithm_has_a_strategy(self):
        """A new entry in settings.DEDUPE_ALGOS without a strategy must fail here, not at import time."""
        for algorithm in settings.DEDUPE_ALGOS:
            self.assertIn(algorithm, deduplication.DEDUPLICATION_STRATEGIES)

    def test_strategies_are_wired_to_their_algorithm(self):
        expected = {
            settings.DEDUPE_ALGO_HASH_CODE: (deduplication.match_batch_hash_code, deduplication._dedupe_batch_hash_code),
            settings.DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL: (deduplication.match_batch_unique_id, deduplication._dedupe_batch_unique_id),
            settings.DEDUPE_ALGO_UNIQUE_ID_FROM_TOOL_OR_HASH_CODE: (deduplication.match_batch_uid_or_hash, deduplication._dedupe_batch_uid_or_hash),
            settings.DEDUPE_ALGO_LEGACY: (deduplication.match_batch_legacy, deduplication._dedupe_batch_legacy),
        }
        for algorithm, (match, dedupe) in expected.items():
            strategy = deduplication.get_deduplication_strategy(algorithm)
            self.assertIs(strategy.match_batch, match)
            self.assertIs(strategy.dedupe_batch, dedupe)

    def test_unknown_algorithm_falls_back_to_legacy(self):
        self.assertIs(
            deduplication.get_deduplication_strategy("not_an_algorithm"),
            deduplication.DEDUPLICATION_STRATEGIES[settings.DEDUPE_ALGO_LEGACY],
        )
