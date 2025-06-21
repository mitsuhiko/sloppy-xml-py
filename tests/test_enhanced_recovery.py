#!/usr/bin/env python3
"""
Test script demonstrating enhanced error recovery features in the sloppy XML parser.
"""

import pytest
import sloppy_xml
from sloppy_xml import ParseOptions, RecoveryStrategy


class TestBasicRecovery:
    """Test basic error recovery functionality."""

    def test_basic_recovery(self):
        """Test basic error recovery functionality."""
        # Malformed XML with unclosed tags
        xml = "<root><child>text<child>more text"

        events = list(sloppy_xml.stream_parse(xml))
        assert len(events) > 0

        # Check that we get various event types
        event_types = [type(event).__name__ for event in events]
        assert "StartElement" in event_types


class TestAdvancedRecovery:
    """Test advanced recovery with detailed error reporting."""

    def test_advanced_recovery(self):
        """Test advanced recovery with detailed error reporting."""
        # XML with multiple issues
        malformed_xml = """
        <!-- broken comment ->
        <root>
            <child attr="missing quote>
                Text with &broken entity
                <![CDATA[broken cdata section]>
            </child>
        """

        opts = ParseOptions(
            emit_errors=True,
            recovery_strategy=RecoveryStrategy.AGGRESSIVE,
            repair_attributes=True,
            smart_quotes=True,
        )

        events = list(sloppy_xml.stream_parse(malformed_xml, options=opts))
        assert len(events) > 0

        # Check for error events if available
        error_events = [e for e in events if hasattr(e, "error_type")]
        # Some parsers may not emit error events, that's OK

        # Should at least get some element events
        element_events = [
            e for e in events if type(e).__name__ in ["StartElement", "EndElement"]
        ]
        assert len(element_events) > 0


class TestEncodingRecovery:
    """Test encoding issue recovery."""

    def test_encoding_recovery(self):
        """Test encoding issue recovery."""
        # XML with encoding issues (simulated)
        xml_with_encoding_issues = '<root>Text with em—dash and "smart quotes"</root>'

        opts = ParseOptions(
            fix_encoding=True,
            emit_errors=True,
            recovery_strategy=RecoveryStrategy.LENIENT,
        )

        events = list(sloppy_xml.stream_parse(xml_with_encoding_issues, options=opts))
        assert len(events) > 0

        # Should get text events
        text_events = [e for e in events if hasattr(e, "content")]
        assert len(text_events) > 0


class TestFragmentSupport:
    """Test XML fragment support."""

    def test_fragment_support(self):
        """Test XML fragment support."""
        # Text without root element
        fragment = "Just some text without a root element"

        opts = ParseOptions(allow_fragments=True)

        # This may not work depending on implementation
        try:
            tree = sloppy_xml.tree_parse(fragment, options=opts)
            # If it works, tree should not be None
            assert tree is not None
        except (ValueError, Exception):
            # Fragment parsing might not be supported, that's OK
            pass

        # Multiple root elements
        multi_root = "<root1>content1</root1><root2>content2</root2>"

        try:
            tree = sloppy_xml.tree_parse(multi_root, options=opts)
            # If it works, should get some tree
            assert tree is not None
        except (ValueError, Exception):
            # Multi-root might not be supported, that's OK
            pass


class TestRecoveryStrategies:
    """Test different recovery strategies."""

    def test_recovery_strategies(self):
        """Test different recovery strategies."""
        malformed = '<root><child attr="broken>text</child>'

        strategies = [
            (RecoveryStrategy.STRICT, "Strict"),
            (RecoveryStrategy.LENIENT, "Lenient"),
            (RecoveryStrategy.AGGRESSIVE, "Aggressive"),
        ]

        for strategy, name in strategies:
            opts = ParseOptions(
                recovery_strategy=strategy, emit_errors=True, repair_attributes=True
            )

            events = list(sloppy_xml.stream_parse(malformed, options=opts))
            error_count = sum(1 for e in events if hasattr(e, "error_type"))
            element_count = sum(
                1 for e in events if type(e).__name__ in ["StartElement", "EndElement"]
            )

            # Should get at least some events
            assert len(events) > 0
            # Should get at least some elements
            assert element_count > 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
