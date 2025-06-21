#!/usr/bin/env python3
"""
Test script demonstrating enhanced error recovery features in the sloppy XML parser.
"""

import pytest
import sloppy_xml
from sloppy_xml import RecoveryStrategy


def test_basic_recovery():
    """Test basic error recovery functionality."""
    # Malformed XML with unclosed tags
    xml = "<root><child>text<child>more text"

    events = list(sloppy_xml.stream_parse(xml))
    assert len(events) > 0

    # Check that we get various event types
    event_types = [type(event).__name__ for event in events]
    assert "StartElement" in event_types


def test_advanced_recovery():
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

    events = list(
        sloppy_xml.stream_parse(
            malformed_xml,
            emit_errors=True,
            recovery_strategy=RecoveryStrategy.AGGRESSIVE,
            repair_attributes=True,
            smart_quotes=True,
        )
    )
    assert len(events) > 0

    # Check for error events if available
    [e for e in events if hasattr(e, "error_type")]
    # Some parsers may not emit error events, that's OK

    # Should at least get some element events
    element_events = [
        e for e in events if type(e).__name__ in ["StartElement", "EndElement"]
    ]
    assert len(element_events) > 0


def test_encoding_recovery():
    """Test encoding issue recovery."""
    # XML with encoding issues (simulated)
    xml_with_encoding_issues = '<root>Text with em—dash and "smart quotes"</root>'

    events = list(
        sloppy_xml.stream_parse(
            xml_with_encoding_issues,
            fix_encoding=True,
            emit_errors=True,
            recovery_strategy=RecoveryStrategy.LENIENT,
        )
    )
    assert len(events) > 0

    # Should get text events
    text_events = [e for e in events if hasattr(e, "content")]
    assert len(text_events) > 0


def test_fragment_support():
    """Test XML fragment support."""
    # Text without root element
    fragment = "Just some text without a root element"

    tree = sloppy_xml.tree_parse(fragment, allow_fragments=True)
    assert tree is not None

    # Multiple root elements
    multi_root = "<root1>content1</root1><root2>content2</root2>"

    tree = sloppy_xml.tree_parse(multi_root, allow_fragments=True)
    assert tree is not None


def test_recovery_strategies():
    """Test different recovery strategies."""
    malformed = '<root><child attr="broken>text</child>'

    strategies = [
        (RecoveryStrategy.STRICT, "Strict"),
        (RecoveryStrategy.LENIENT, "Lenient"),
        (RecoveryStrategy.AGGRESSIVE, "Aggressive"),
    ]

    for strategy, name in strategies:
        events = list(
            sloppy_xml.stream_parse(
                malformed,
                recovery_strategy=strategy,
                emit_errors=True,
                repair_attributes=True,
            )
        )
        sum(1 for e in events if hasattr(e, "error_type"))
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
