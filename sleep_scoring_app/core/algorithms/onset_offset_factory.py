"""
Onset/offset rule factory for dependency injection.

Provides centralized rule instantiation and configuration management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sleep_scoring_app.core.algorithms.config import SleepRulesConfig
from sleep_scoring_app.core.algorithms.onset_offset_protocol import OnsetOffsetRule
from sleep_scoring_app.core.algorithms.sleep_rules import SleepRules
from sleep_scoring_app.core.algorithms.tudor_locke import TudorLockeConfig, TudorLockeRule

if TYPE_CHECKING:
    from sleep_scoring_app.utils.config import AppConfig

logger = logging.getLogger(__name__)


class OnsetOffsetRuleFactory:
    """
    Factory for creating onset/offset rule instances.

    Manages rule instantiation, configuration, and registration.
    Enables dependency injection throughout the application.
    """

    _rules: dict[str, type] = {
        "consecutive_3_5": SleepRules,
        "consecutive_5_10": SleepRules,  # Same class with different config
        "tudor_locke_2014": TudorLockeRule,
    }

    # Default configurations for known rule variants
    _default_configs: dict[str, SleepRulesConfig | TudorLockeConfig] = {
        "consecutive_3_5": SleepRulesConfig(
            onset_consecutive_minutes=3,
            offset_consecutive_minutes=5,
            search_extension_minutes=5,
            require_wake_after_offset=True,
        ),
        "consecutive_5_10": SleepRulesConfig(
            onset_consecutive_minutes=5,
            offset_consecutive_minutes=10,
            search_extension_minutes=5,
            require_wake_after_offset=True,
        ),
        "tudor_locke_2014": TudorLockeConfig(
            onset_consecutive_minutes=5,
            offset_consecutive_wake_minutes=10,
            search_extension_minutes=5,
            min_sleep_period_minutes=160,
            max_sleep_period_minutes=1440,
        ),
    }

    @classmethod
    def create(cls, rule_id: str, config: AppConfig | None = None) -> OnsetOffsetRule:
        """
        Create an onset/offset rule instance.

        Args:
            rule_id: Rule identifier (e.g., "consecutive_3_5", "tudor_locke_2014")
            config: Optional application config for parameter initialization

        Returns:
            Configured rule instance

        Raises:
            ValueError: If rule_id is not registered
        """
        if rule_id not in cls._rules:
            available = ", ".join(cls._rules.keys())
            msg = f"Unknown onset/offset rule '{rule_id}'. Available: {available}"
            raise ValueError(msg)

        rule_class = cls._rules[rule_id]

        # Get rule-specific configuration
        rule_config = cls._default_configs.get(rule_id, SleepRulesConfig())

        # Override with app config if provided
        if config and hasattr(config, "onset_offset_rule_config"):
            rule_config = config.onset_offset_rule_config

        # Instantiate rule with appropriate config
        if rule_id.startswith("consecutive_"):
            return rule_class(config=rule_config)

        if rule_id == "tudor_locke_2014":
            tudor_config = cls._default_configs.get(rule_id, TudorLockeConfig())
            return rule_class(config=tudor_config)

        # Default instantiation for other rules
        return rule_class()

    @classmethod
    def get_available_rules(cls) -> dict[str, str]:
        """
        Get all available onset/offset rules.

        Returns:
            Dictionary mapping rule_id to display name
        """
        result = {}
        for rule_id in cls._rules:
            # Instantiate temporarily to get name
            if rule_id in cls._default_configs:
                instance = cls._rules[rule_id](config=cls._default_configs[rule_id])
            else:
                instance = cls._rules[rule_id]()
            result[rule_id] = instance.name

        return result

    @classmethod
    def get_default_rule_id(cls) -> str:
        """
        Get the default rule identifier.

        Returns:
            Default rule ID ("consecutive_3_5")
        """
        return "consecutive_3_5"

    @classmethod
    def register_rule(
        cls,
        rule_id: str,
        rule_class: type,
        default_config: SleepRulesConfig | None = None,
    ) -> None:
        """
        Register a new onset/offset rule.

        Args:
            rule_id: Unique identifier for the rule
            rule_class: Rule class implementing OnsetOffsetRule protocol
            default_config: Optional default configuration

        Raises:
            ValueError: If rule_id already registered
        """
        if rule_id in cls._rules:
            msg = f"Onset/offset rule '{rule_id}' is already registered"
            raise ValueError(msg)

        cls._rules[rule_id] = rule_class
        if default_config:
            cls._default_configs[rule_id] = default_config

        logger.info("Registered new onset/offset rule: %s", rule_id)

    @classmethod
    def get_rule_description(cls, rule_id: str) -> str:
        """
        Get description for a specific rule.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule description

        Raises:
            ValueError: If rule_id not registered
        """
        if rule_id not in cls._rules:
            available = ", ".join(cls._rules.keys())
            msg = f"Unknown onset/offset rule '{rule_id}'. Available: {available}"
            raise ValueError(msg)

        # Create temporary instance to get description
        rule = cls.create(rule_id)
        return rule.description
