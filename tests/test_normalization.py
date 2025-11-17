"""
Tests for address normalization functionality.

Tests ensure that addresses are normalized consistently for matching and deduplication.
"""

import pytest
from src.normalization import (
    normalize_address,
    normalize_street_name,
    clean_whitespace,
)


class TestNormalizeAddress:
    """Test cases for the normalize_address function."""

    def test_lowercase_to_uppercase(self):
        """Test that lowercase addresses are converted to uppercase."""
        assert normalize_address("123 main street") == "123 MAIN ST"

    def test_mixed_case_to_uppercase(self):
        """Test that mixed case addresses are converted to uppercase."""
        assert normalize_address("45 Elm Avenue") == "45 ELM AVE"

    def test_extra_whitespace_removal(self):
        """Test that multiple spaces are reduced to single spaces."""
        assert normalize_address("45  elm   avenue") == "45 ELM AVE"

    def test_leading_trailing_whitespace(self):
        """Test that leading and trailing whitespace is removed."""
        assert normalize_address("  100 park street  ") == "100 PARK ST"

    def test_street_type_abbreviations(self):
        """Test that common street types are abbreviated."""
        test_cases = [
            ("123 main street", "123 MAIN ST"),
            ("456 oak avenue", "456 OAK AVE"),
            ("789 maple boulevard", "789 MAPLE BLVD"),
            ("100 pine drive", "100 PINE DR"),
            ("200 elm lane", "200 ELM LN"),
            ("300 cedar road", "300 CEDAR RD"),
            ("400 birch court", "400 BIRCH CT"),
            ("500 willow place", "500 WILLOW PL"),
            ("600 cherry circle", "600 CHERRY CIR"),
            ("700 walnut terrace", "700 WALNUT TER"),
        ]
        for input_addr, expected in test_cases:
            assert normalize_address(input_addr) == expected

    def test_directional_abbreviations(self):
        """Test that directional indicators are abbreviated."""
        test_cases = [
            ("100 north main street", "100 N MAIN ST"),
            ("200 south oak avenue", "200 S OAK AVE"),
            ("300 east park boulevard", "300 E PARK BLVD"),
            ("400 west elm drive", "400 W ELM DR"),
            ("500 northeast maple lane", "500 NE MAPLE LN"),
            ("600 northwest pine road", "600 NW PINE RD"),
            ("700 southeast cedar court", "700 SE CEDAR CT"),
            ("800 southwest birch place", "800 SW BIRCH PL"),
        ]
        for input_addr, expected in test_cases:
            assert normalize_address(input_addr) == expected

    def test_no_duplicate_spaces_in_output(self):
        """Test that output never contains duplicate spaces."""
        test_inputs = [
            "123  main  street",
            "456   oak    avenue",
            "789     maple      boulevard",
        ]
        for addr in test_inputs:
            result = normalize_address(addr)
            assert "  " not in result, f"Found duplicate spaces in: {result}"

    def test_empty_string(self):
        """Test that empty strings are handled gracefully."""
        assert normalize_address("") == ""

    def test_none_input(self):
        """Test that None input is handled gracefully."""
        assert normalize_address(None) == ""

    def test_whitespace_only(self):
        """Test that whitespace-only strings are handled."""
        assert normalize_address("   ") == ""

    def test_trailing_punctuation_removed(self):
        """Test that trailing punctuation is removed."""
        test_cases = [
            ("123 main street.", "123 MAIN ST"),
            ("456 oak avenue,", "456 OAK AVE"),
            ("789 maple blvd;", "789 MAPLE BLVD"),
        ]
        for input_addr, expected in test_cases:
            assert normalize_address(input_addr) == expected

    def test_complex_address(self):
        """Test normalization of complex addresses."""
        input_addr = "  100  North  Park  Boulevard  "
        expected = "100 N PARK BLVD"
        assert normalize_address(input_addr) == expected

    def test_numeric_only(self):
        """Test that numeric-only addresses work."""
        assert normalize_address("12345") == "12345"

    def test_special_characters(self):
        """Test that addresses with special characters are handled."""
        # Should preserve hyphens and other valid characters
        input_addr = "123-A Main Street"
        result = normalize_address(input_addr)
        assert "MAIN ST" in result
        assert "123-A" in result


class TestNormalizeStreetName:
    """Test cases for the normalize_street_name function."""

    def test_street_name_only(self):
        """Test normalizing street name without house number."""
        assert normalize_street_name("main street") == "MAIN ST"

    def test_street_name_with_house_number(self):
        """Test normalizing street name with house number."""
        assert normalize_street_name("elm avenue", "45") == "45 ELM AVE"

    def test_empty_street_name(self):
        """Test that empty street names are handled."""
        assert normalize_street_name("") == ""

    def test_none_street_name(self):
        """Test that None street names are handled."""
        assert normalize_street_name(None) == ""

    def test_house_number_with_empty_street(self):
        """Test house number with empty street name."""
        assert normalize_street_name("", "123") == ""


class TestCleanWhitespace:
    """Test cases for the clean_whitespace function."""

    def test_multiple_spaces_reduced(self):
        """Test that multiple spaces are reduced to single space."""
        assert clean_whitespace("hello    world") == "hello world"

    def test_leading_trailing_removed(self):
        """Test that leading/trailing whitespace is removed."""
        assert clean_whitespace("  test  ") == "test"

    def test_tabs_converted_to_spaces(self):
        """Test that tabs are converted to single spaces."""
        assert clean_whitespace("hello\t\tworld") == "hello world"

    def test_newlines_converted_to_spaces(self):
        """Test that newlines are converted to single spaces."""
        assert clean_whitespace("hello\n\nworld") == "hello world"

    def test_mixed_whitespace(self):
        """Test mixed whitespace types are normalized."""
        assert clean_whitespace("  hello \t world \n test  ") == "hello world test"

    def test_empty_string(self):
        """Test empty string handling."""
        assert clean_whitespace("") == ""

    def test_none_input(self):
        """Test None input handling."""
        assert clean_whitespace(None) == ""


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_address(self):
        """Test that very long addresses are handled."""
        long_addr = "12345 " + ("very " * 50) + "long street"
        result = normalize_address(long_addr)
        assert "LONG ST" in result
        assert "  " not in result

    def test_unicode_characters(self):
        """Test that unicode characters are preserved."""
        # Some cities have unicode characters in street names
        addr = "123 José Street"
        result = normalize_address(addr)
        assert "JOSÉ" in result
        assert "ST" in result

    def test_numbers_in_street_names(self):
        """Test that numbers in street names are preserved."""
        test_cases = [
            ("123 1st street", "123 1ST ST"),
            ("456 2nd avenue", "456 2ND AVE"),
            ("789 3rd boulevard", "789 3RD BLVD"),
        ]
        for input_addr, expected in test_cases:
            assert normalize_address(input_addr) == expected
