"""
Unit tests for OnsetOffsetRuleFactory dependency injection.

Tests the factory pattern implementation for sleep onset/offset detection rules.
"""

from __future__ import annotations

import pytest

from sleep_scoring_app.core.algorithms.onset_offset_factory import OnsetOffsetRuleFactory
from sleep_scoring_app.core.algorithms.onset_offset_protocol import OnsetOffsetRule


class TestOnsetOffsetRuleFactoryCreation:
    """Tests for rule creation via factory."""

    def test_create_consecutive_3_5(self) -> None:
        """Test creating consecutive 3/5 minutes rule."""
        rule = OnsetOffsetRuleFactory.create("consecutive_3_5")
        assert rule is not None
        assert rule.name == "Consecutive 3/5 Minutes"
        assert isinstance(rule, OnsetOffsetRule)

    def test_create_consecutive_5_10(self) -> None:
        """Test creating consecutive 5/10 minutes rule."""
        rule = OnsetOffsetRuleFactory.create("consecutive_5_10")
        assert rule is not None
        assert rule.name == "Consecutive 5/10 Minutes"
        assert isinstance(rule, OnsetOffsetRule)

    def test_create_tudor_locke_2014(self) -> None:
        """Test creating Tudor-Locke 2014 rule."""
        rule = OnsetOffsetRuleFactory.create("tudor_locke_2014")
        assert rule is not None
        assert rule.name == "Tudor-Locke (5/10)"
        assert isinstance(rule, OnsetOffsetRule)

    def test_create_unknown_rule_raises(self) -> None:
        """Test that creating unknown rule raises ValueError."""
        with pytest.raises(ValueError, match="Unknown onset/offset rule"):
            OnsetOffsetRuleFactory.create("nonexistent_rule")

    def test_create_returns_new_instance_each_time(self) -> None:
        """Test that each create call returns a new instance."""
        rule1 = OnsetOffsetRuleFactory.create("consecutive_3_5")
        rule2 = OnsetOffsetRuleFactory.create("consecutive_3_5")
        assert rule1 is not rule2


class TestOnsetOffsetRuleFactoryRegistry:
    """Tests for factory registry operations."""

    def test_get_available_rules(self) -> None:
        """Test listing available rules."""
        available = OnsetOffsetRuleFactory.get_available_rules()
        assert isinstance(available, dict)
        assert "consecutive_3_5" in available
        assert "consecutive_5_10" in available
        assert "tudor_locke_2014" in available

    def test_get_available_rules_returns_display_names(self) -> None:
        """Test that available rules dict has display names as values."""
        available = OnsetOffsetRuleFactory.get_available_rules()
        assert available["consecutive_3_5"] == "Consecutive 3/5 Minutes"
        assert available["consecutive_5_10"] == "Consecutive 5/10 Minutes"
        assert available["tudor_locke_2014"] == "Tudor-Locke (5/10)"

    def test_get_default_rule_id(self) -> None:
        """Test getting default rule ID."""
        default_id = OnsetOffsetRuleFactory.get_default_rule_id()
        assert default_id == "consecutive_3_5"


class TestOnsetOffsetRuleBehavior:
    """Tests for rule behavior from factory."""

    def test_consecutive_3_5_parameters(self) -> None:
        """Test consecutive 3/5 rule has correct parameters."""
        rule = OnsetOffsetRuleFactory.create("consecutive_3_5")
        params = rule.get_parameters()
        assert params["onset_consecutive_minutes"] == 3
        assert params["offset_consecutive_minutes"] == 5

    def test_consecutive_5_10_parameters(self) -> None:
        """Test consecutive 5/10 rule has correct parameters."""
        rule = OnsetOffsetRuleFactory.create("consecutive_5_10")
        params = rule.get_parameters()
        assert params["onset_consecutive_minutes"] == 5
        assert params["offset_consecutive_minutes"] == 10

    def test_tudor_locke_parameters(self) -> None:
        """Test Tudor-Locke rule has correct parameters."""
        rule = OnsetOffsetRuleFactory.create("tudor_locke_2014")
        params = rule.get_parameters()
        assert params["onset_consecutive_minutes"] == 5
        assert params["offset_consecutive_wake_minutes"] == 10

    def test_all_rules_have_apply_rules_method(self) -> None:
        """Test all rules implement apply_rules method."""
        for rule_id in OnsetOffsetRuleFactory.get_available_rules():
            rule = OnsetOffsetRuleFactory.create(rule_id)
            assert hasattr(rule, "apply_rules")
            assert callable(rule.apply_rules)

    def test_all_rules_have_name_property(self) -> None:
        """Test all rules have name property."""
        for rule_id in OnsetOffsetRuleFactory.get_available_rules():
            rule = OnsetOffsetRuleFactory.create(rule_id)
            assert hasattr(rule, "name")
            assert isinstance(rule.name, str)
            assert len(rule.name) > 0

    def test_all_rules_have_identifier_property(self) -> None:
        """Test all rules have identifier property."""
        for rule_id in OnsetOffsetRuleFactory.get_available_rules():
            rule = OnsetOffsetRuleFactory.create(rule_id)
            assert hasattr(rule, "identifier")
            assert isinstance(rule.identifier, str)

    def test_all_rules_have_description_property(self) -> None:
        """Test all rules have description property."""
        for rule_id in OnsetOffsetRuleFactory.get_available_rules():
            rule = OnsetOffsetRuleFactory.create(rule_id)
            assert hasattr(rule, "description")
            assert isinstance(rule.description, str)

    def test_all_rules_have_get_parameters(self) -> None:
        """Test all rules implement get_parameters."""
        for rule_id in OnsetOffsetRuleFactory.get_available_rules():
            rule = OnsetOffsetRuleFactory.create(rule_id)
            assert hasattr(rule, "get_parameters")
            params = rule.get_parameters()
            assert isinstance(params, dict)


class TestOnsetOffsetRuleFactoryWithConfig:
    """Tests for factory with config parameter."""

    def test_create_with_none_config(self) -> None:
        """Test creating rule with None config."""
        rule = OnsetOffsetRuleFactory.create("consecutive_3_5", config=None)
        assert rule is not None

    def test_create_ignores_config_for_now(self) -> None:
        """Test that config parameter is reserved for future use."""
        rule = OnsetOffsetRuleFactory.create("tudor_locke_2014", config=None)
        assert rule.name == "Tudor-Locke (5/10)"
