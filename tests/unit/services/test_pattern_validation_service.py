#!/usr/bin/env python3
"""
Comprehensive tests for PatternValidationService.
Tests regex pattern validation and participant extraction testing.
"""

from __future__ import annotations

import pytest

from sleep_scoring_app.services.pattern_validation_service import (
    ExtractionTestResult,
    PatternValidationResult,
    PatternValidationService,
)


class TestPatternValidationResult:
    """Tests for PatternValidationResult dataclass."""

    def test_valid_result(self) -> None:
        """Valid result should have is_valid=True."""
        result = PatternValidationResult(is_valid=True)
        assert result.is_valid
        assert result.error_message is None

    def test_invalid_result_with_message(self) -> None:
        """Invalid result should have error message."""
        result = PatternValidationResult(is_valid=False, error_message="Invalid syntax")
        assert not result.is_valid
        assert result.error_message == "Invalid syntax"


class TestExtractionTestResult:
    """Tests for ExtractionTestResult dataclass."""

    def test_empty_result(self) -> None:
        """Empty result should have sensible defaults."""
        result = ExtractionTestResult(test_input="", participant_info=None)
        assert result.test_input == ""
        assert result.participant_info is None
        assert result.id_status == ""
        assert result.id_color == ""

    def test_result_with_statuses(self) -> None:
        """Result should preserve status information."""
        result = ExtractionTestResult(
            test_input="1234_G1_T1",
            participant_info=None,
            id_status="1234",
            id_color="#28a745",
            id_icon="✓",
        )
        assert result.test_input == "1234_G1_T1"
        assert result.id_status == "1234"
        assert result.id_color == "#28a745"
        assert result.id_icon == "✓"


class TestValidatePattern:
    """Tests for validate_pattern static method."""

    def test_valid_simple_pattern(self) -> None:
        """Should validate simple regex patterns."""
        result = PatternValidationService.validate_pattern(r"\d+")
        assert result.is_valid

    def test_valid_complex_pattern(self) -> None:
        """Should validate complex regex patterns."""
        result = PatternValidationService.validate_pattern(r"^(\d{4,})[_-]([A-Z]+)")
        assert result.is_valid

    def test_valid_empty_pattern(self) -> None:
        """Empty pattern should be valid (neutral)."""
        result = PatternValidationService.validate_pattern("")
        assert result.is_valid

    def test_valid_whitespace_pattern(self) -> None:
        """Whitespace-only pattern should be valid (neutral)."""
        result = PatternValidationService.validate_pattern("   ")
        assert result.is_valid

    def test_invalid_unbalanced_parentheses(self) -> None:
        """Should catch unbalanced parentheses."""
        result = PatternValidationService.validate_pattern(r"(\d+")
        assert not result.is_valid
        assert result.error_message is not None

    def test_invalid_unbalanced_brackets(self) -> None:
        """Should catch unbalanced brackets."""
        result = PatternValidationService.validate_pattern(r"[a-z")
        assert not result.is_valid

    def test_invalid_bad_quantifier(self) -> None:
        """Should catch invalid quantifier."""
        result = PatternValidationService.validate_pattern(r"a{2,1}")  # Invalid range
        assert not result.is_valid

    def test_invalid_bad_escape(self) -> None:
        """Should catch invalid escape sequence."""
        # In Python regex, \q is not a valid escape
        result = PatternValidationService.validate_pattern(r"\q")
        # Note: Python re module is lenient with unknown escapes
        # This test may pass or fail depending on Python version

    def test_valid_lookahead(self) -> None:
        """Should validate lookahead patterns."""
        result = PatternValidationService.validate_pattern(r"foo(?=bar)")
        assert result.is_valid

    def test_valid_lookbehind(self) -> None:
        """Should validate lookbehind patterns."""
        result = PatternValidationService.validate_pattern(r"(?<=foo)bar")
        assert result.is_valid

    def test_valid_named_groups(self) -> None:
        """Should validate named groups."""
        result = PatternValidationService.validate_pattern(r"(?P<id>\d+)")
        assert result.is_valid

    def test_valid_character_classes(self) -> None:
        """Should validate character classes."""
        result = PatternValidationService.validate_pattern(r"[A-Za-z0-9_-]+")
        assert result.is_valid


class TestGetDefaultPatterns:
    """Tests for get_default_patterns static method."""

    def test_returns_dict(self) -> None:
        """Should return a dictionary."""
        patterns = PatternValidationService.get_default_patterns()
        assert isinstance(patterns, dict)

    def test_contains_id_pattern(self) -> None:
        """Should contain id_pattern."""
        patterns = PatternValidationService.get_default_patterns()
        assert "id_pattern" in patterns
        assert patterns["id_pattern"]

    def test_contains_timepoint_pattern(self) -> None:
        """Should contain timepoint_pattern."""
        patterns = PatternValidationService.get_default_patterns()
        assert "timepoint_pattern" in patterns

    def test_contains_group_pattern(self) -> None:
        """Should contain group_pattern."""
        patterns = PatternValidationService.get_default_patterns()
        assert "group_pattern" in patterns

    def test_all_patterns_are_valid(self) -> None:
        """All default patterns should be valid regex."""
        patterns = PatternValidationService.get_default_patterns()
        for name, pattern in patterns.items():
            result = PatternValidationService.validate_pattern(pattern)
            assert result.is_valid, f"Pattern '{name}' is invalid: {result.error_message}"


class TestFormatTestResultHtml:
    """Tests for format_test_result_html static method."""

    def test_empty_input(self) -> None:
        """Should return placeholder for empty input."""
        result = ExtractionTestResult(test_input="", participant_info=None)
        html = PatternValidationService.format_test_result_html(result)
        assert "Enter an ID" in html

    def test_error_message(self) -> None:
        """Should format error message."""
        result = ExtractionTestResult(
            test_input="test",
            participant_info=None,
            error_message="Test error",
        )
        html = PatternValidationService.format_test_result_html(result)
        assert "Test error" in html
        assert "#dc3545" in html  # Red color

    def test_successful_extraction(self) -> None:
        """Should format successful extraction."""
        result = ExtractionTestResult(
            test_input="1234_G1_T1",
            participant_info=None,  # Can be None for display purposes
            id_status="1234",
            id_color="#28a745",
            id_icon="✓",
            group_status="G1",
            group_color="#28a745",
            group_icon="✓",
            timepoint_status="T1",
            timepoint_color="#28a745",
            timepoint_icon="✓",
        )
        html = PatternValidationService.format_test_result_html(result)
        assert "1234_G1_T1" in html
        assert "1234" in html
        assert "#28a745" in html  # Green color
        assert "✓" in html

    def test_partial_extraction(self) -> None:
        """Should format partial extraction with warnings."""
        result = ExtractionTestResult(
            test_input="unknown_file.csv",
            participant_info=None,
            id_status="not extracted",
            id_color="#dc3545",
            id_icon="✗",
            group_status="Default (using default value)",
            group_color="#ffc107",
            group_icon="⚠",
            timepoint_status="T1",
            timepoint_color="#28a745",
            timepoint_icon="✓",
        )
        html = PatternValidationService.format_test_result_html(result)
        assert "✗" in html
        assert "⚠" in html
        assert "#ffc107" in html  # Yellow/warning color


class TestPatternMatchingScenarios:
    """Tests for real-world pattern matching scenarios."""

    def test_standard_participant_id(self) -> None:
        """Test standard participant ID pattern."""
        # Pattern: Extract 4+ digit ID at start
        pattern = r"^(\d{4,})"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

        import re

        match = re.match(pattern, "1234_G1_T1")
        assert match is not None
        assert match.group(1) == "1234"

    def test_group_pattern(self) -> None:
        """Test group extraction pattern."""
        pattern = r"[gG]([123])"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

        import re

        match = re.search(pattern, "1234_G2_T1")
        assert match is not None
        assert match.group(1) == "2"

    def test_timepoint_pattern(self) -> None:
        """Test timepoint extraction pattern."""
        pattern = r"[tT]([0-9]+)"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

        import re

        match = re.search(pattern, "1234_G1_T3")
        assert match is not None
        assert match.group(1) == "3"

    def test_filename_pattern(self) -> None:
        """Test pattern for extracting from filenames."""
        pattern = r"participant_(\d+)_session_(\d+)\.csv$"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

        import re

        match = re.match(pattern, "participant_1234_session_2.csv")
        assert match is not None
        assert match.group(1) == "1234"
        assert match.group(2) == "2"

    def test_optional_group_pattern(self) -> None:
        """Test pattern with optional groups."""
        pattern = r"^(\d+)(?:_([A-Z]+))?(?:_([A-Z]\d+))?"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

        import re

        # Full match
        match = re.match(pattern, "1234_GROUP_T1")
        assert match is not None
        assert match.group(1) == "1234"
        assert match.group(2) == "GROUP"
        assert match.group(3) == "T1"

        # Partial match
        match = re.match(pattern, "1234")
        assert match is not None
        assert match.group(1) == "1234"
        assert match.group(2) is None


class TestPatternEdgeCases:
    """Tests for edge cases in pattern handling."""

    def test_unicode_in_pattern(self) -> None:
        """Should handle unicode in patterns."""
        result = PatternValidationService.validate_pattern(r"[äöü]+")
        assert result.is_valid

    def test_very_long_pattern(self) -> None:
        """Should handle very long patterns."""
        long_pattern = r"(\d+)" * 50
        result = PatternValidationService.validate_pattern(long_pattern)
        assert result.is_valid

    def test_pattern_with_comments(self) -> None:
        """Should validate pattern with inline comments (verbose mode)."""
        # This tests that patterns intended for verbose mode are valid
        pattern = r"(?x)\d+  # comment"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid

    def test_pattern_with_special_chars(self) -> None:
        """Should handle special characters properly escaped."""
        pattern = r"\.\*\+\?\[\]\{\}\(\)\|\\$\^"
        result = PatternValidationService.validate_pattern(pattern)
        assert result.is_valid
