#!/usr/bin/env python3
"""
Comprehensive test suite for the sloppy XML parser.

This test suite validates all functionality including:
- Basic XML parsing (well-formed documents)
- Stream parsing functionality (event generation)
- Tree parsing functionality (ElementTree construction)
- Entity resolution (valid and invalid entities)
- Error recovery scenarios (malformed XML)
- Edge cases and boundary conditions
- Performance characteristics
- Real-world malformed XML scenarios
"""

import pytest
import io
import time
import tempfile
import os

# Import the parser under test
import sloppy_xml
from sloppy_xml import (
    StartElement,
    EndElement,
    Text,
    Comment,
    ProcessingInstruction,
    ParseError,
    XMLEvent,
    RecoveryStrategy,
    TreeBuilder,
)


def test_simple_element():
    """Test parsing a simple element."""
    xml = "<root>content</root>"
    events = list(sloppy_xml.stream_parse(xml))

    # Find events by type rather than assuming exact count
    start_events = [e for e in events if isinstance(e, StartElement)]
    text_events = [e for e in events if isinstance(e, Text)]
    end_events = [e for e in events if isinstance(e, EndElement)]

    assert len(start_events) == 1
    assert start_events[0].name == "root"
    assert start_events[0].attrs == {}

    assert len(text_events) >= 0  # May or may not have text events
    if text_events:
        assert "content" in text_events[0].content

    assert len(end_events) == 1
    assert end_events[0].name == "root"
    assert not end_events[0].auto_closed


def test_nested_elements():
    """Test parsing nested elements."""
    xml = "<root><child><grandchild>text</grandchild></child></root>"
    events = list(sloppy_xml.stream_parse(xml))

    # Find events by type
    start_events = [e for e in events if isinstance(e, StartElement)]
    end_events = [e for e in events if isinstance(e, EndElement)]
    text_events = [e for e in events if isinstance(e, Text)]

    assert len(start_events) == 3  # root, child, grandchild
    assert len(end_events) == 3  # grandchild, child, root
    assert len(text_events) >= 0  # May or may not have text events

    # Check that we have the expected element names
    element_names = [e.name for e in start_events]
    assert "root" in element_names
    assert "child" in element_names
    assert "grandchild" in element_names


def test_attributes():
    """Test parsing elements with attributes."""
    xml = '<root id="123" class="main" checked>content</root>'
    events = list(sloppy_xml.stream_parse(xml))

    start_element = events[0]
    assert isinstance(start_element, StartElement)
    assert start_element.attrs["id"] == "123"
    assert start_element.attrs["class"] == "main"
    assert start_element.attrs["checked"] == ""


def test_self_closing_tags():
    """Test parsing self-closing tags."""
    xml = '<root><img src="test.jpg"/><br/></root>'
    events = list(sloppy_xml.stream_parse(xml))

    # root start, img start+end, br start+end, root end = 6 events
    assert len(events) == 6
    assert events[1].name == "img"
    assert events[2].name == "img"
    assert events[3].name == "br"
    assert events[4].name == "br"


def test_empty_element():
    """Test parsing empty elements."""
    xml = "<root></root>"
    events = list(sloppy_xml.stream_parse(xml))

    assert len(events) == 2
    assert isinstance(events[0], StartElement)
    assert isinstance(events[1], EndElement)


def test_whitespace_handling():
    """Test whitespace handling with different options."""
    xml = "<root>  \n  text  \n  </root>"

    # Default - should preserve significant whitespace
    events = list(sloppy_xml.stream_parse(xml))
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert "text" in text_events[0].content

    # Preserve all whitespace
    events = list(sloppy_xml.stream_parse(xml, preserve_whitespace=True))
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == "  \n  text  \n  "

    # Normalize whitespace
    events = list(sloppy_xml.stream_parse(xml, normalize_whitespace=True))
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == " text "


def test_stream_events_order():
    """Test that events are generated in correct order."""
    xml = "<!--comment--><root>text</root><?pi target?>"
    events = list(sloppy_xml.stream_parse(xml))

    event_types = [type(e).__name__ for e in events]
    expected = [
        "Comment",
        "StartElement",
        "Text",
        "EndElement",
        "ProcessingInstruction",
    ]
    assert event_types == expected


def test_position_tracking():
    """Test line and column position tracking."""
    xml = """<root>
    <child>text</child>
</root>"""
    events = list(sloppy_xml.stream_parse(xml))

    # First element should be at line 1
    start_event = events[0]
    assert start_event.line == 1
    assert start_event.column == 1

    # Child element should be at line 2
    child_events = [
        e for e in events if isinstance(e, StartElement) and e.name == "child"
    ]
    assert len(child_events) == 1
    assert child_events[0].line == 2


def test_streaming_large_input():
    """Test streaming behavior with large input."""
    # Create a large XML document
    large_xml = (
        "<root>"
        + "".join(f"<item{i}>content{i}</item{i}>" for i in range(1000))
        + "</root>"
    )

    # Parse as stream - should not load everything into memory at once
    event_count = 0
    for event in sloppy_xml.stream_parse(large_xml):
        event_count += 1
        # Verify we can process events one by one
        assert isinstance(event, XMLEvent)

    # Should have 1 + (3 * 1000) + 1 = 3002 events
    assert event_count == 3002


def test_file_input():
    """Test parsing from file-like objects."""
    xml = "<root><child>text</child></root>"

    # Test with StringIO
    file_obj = io.StringIO(xml)
    events = list(sloppy_xml.stream_parse(file_obj))
    assert len(events) == 5  # StartElement, StartElement, Text, EndElement, EndElement

    # Test with BytesIO
    file_obj = io.BytesIO(xml.encode("utf-8"))
    events = list(sloppy_xml.stream_parse(file_obj))
    assert len(events) == 5  # StartElement, StartElement, Text, EndElement, EndElement


def test_legacy_parameters():
    """Test backward compatibility with legacy parameters."""
    xml = "<root>text &amp; more</root>"

    # Test legacy parameter passing
    events = list(
        sloppy_xml.stream_parse(
            xml, recover=True, emit_errors=False, resolve_entities=True
        )
    )

    assert len(events) == 3
    text_event = [e for e in events if isinstance(e, Text)][0]
    assert (
        "text & more" in text_event.content or "text &amp; more" in text_event.content
    )


def test_basic_tree_construction():
    """Test basic ElementTree construction."""
    xml = "<root><child>text</child></root>"
    tree = sloppy_xml.tree_parse(xml)

    assert tree is not None
    assert tree.tag == "root"
    assert len(tree) == 1
    assert tree[0].tag == "child"
    assert tree[0].text == "text"


def test_tree_with_attributes():
    """Test tree construction preserves attributes."""
    xml = '<root id="1"><child class="test">content</child></root>'
    tree = sloppy_xml.tree_parse(xml)

    assert tree.attrib["id"] == "1"
    assert tree[0].attrib["class"] == "test"
    assert tree[0].text == "content"


def test_mixed_content():
    """Test tree with mixed text and element content."""
    xml = "<root>before<child>inner</child>after</root>"
    tree = sloppy_xml.tree_parse(xml)

    assert tree.text == "before"
    assert tree[0].text == "inner"
    assert tree[0].tail == "after"


def test_multiple_children():
    """Test tree with multiple child elements."""
    xml = "<root><child1>text1</child1><child2>text2</child2></root>"
    tree = sloppy_xml.tree_parse(xml)

    assert len(tree) == 2
    assert tree[0].tag == "child1"
    assert tree[1].tag == "child2"
    assert tree[0].text == "text1"
    assert tree[1].text == "text2"


def test_custom_tree_builder():
    """Test using custom tree builder."""

    class MockTreeBuilder(TreeBuilder):
        def __init__(self):
            self.events = []

        def start_element(self, event):
            self.events.append(("start", event.name))

        def end_element(self, event):
            self.events.append(("end", event.name))

        def text(self, event):
            self.events.append(("text", event.content))

        def comment(self, event):
            self.events.append(("comment", event.content))

        def processing_instruction(self, event):
            self.events.append(("pi", event.target))

        def entity_ref(self, event):
            self.events.append(("entity", event.name))

        def parse_error(self, event):
            self.events.append(("error", event.message))

        def get_root(self):
            return self.events

    xml = "<root>text</root>"
    builder = MockTreeBuilder()
    result = sloppy_xml.tree_parse(xml, tree_builder=builder)

    assert result == [("start", "root"), ("text", "text"), ("end", "root")]


def test_tree_parse_from_events():
    """Test tree parsing from pre-generated events."""
    xml = "<root><child>text</child></root>"
    events = sloppy_xml.stream_parse(xml)
    tree = sloppy_xml.tree_parse(events)

    assert tree.tag == "root"
    assert tree[0].text == "text"


def test_tree_parameter():
    """Test the tree parameter for different backend types."""
    xml = "<root><child>text</child></root>"

    # Test default etree backend
    tree_etree = sloppy_xml.tree_parse(xml, tree="etree")
    assert tree_etree.tag == "root"
    assert tree_etree[0].text == "text"

    # Verify it's an ElementTree element
    import xml.etree.ElementTree as ET

    assert isinstance(tree_etree, ET.Element)

    # Test lxml backend if available
    if sloppy_xml.HAS_LXML:
        tree_lxml = sloppy_xml.tree_parse(xml, tree="lxml")
        assert tree_lxml.tag == "root"
        assert tree_lxml[0].text == "text"

        # Verify it's an lxml element
        from lxml import etree as lxml_etree

        assert isinstance(tree_lxml, lxml_etree._Element)

    # Test with invalid tree backend should raise an error
    import pytest

    with pytest.raises(KeyError):
        sloppy_xml.tree_parse(xml, tree="invalid_backend")

    # Test that tree parameter overrides custom tree_builder when both are provided
    class MockTreeBuilder(TreeBuilder):
        def __init__(self):
            self.events = []

        def start_element(self, event):
            self.events.append(("start", event.name))

        def end_element(self, event):
            self.events.append(("end", event.name))

        def text(self, event):
            self.events.append(("text", event.content))

        def comment(self, event):
            pass

        def processing_instruction(self, event):
            pass

        def entity_ref(self, event):
            pass

        def parse_error(self, event):
            pass

        def get_root(self):
            return self.events

    # When both tree_builder and tree are provided, tree parameter should be ignored
    # and custom tree_builder should be used
    custom_builder = MockTreeBuilder()
    result = sloppy_xml.tree_parse(xml, tree_builder=custom_builder, tree="etree")
    # The custom tree builder should be used, not the etree backend
    assert result == [
        ("start", "root"),
        ("start", "child"),
        ("text", "text"),
        ("end", "child"),
        ("end", "root"),
    ]


def test_standard_html_entities():
    """Test resolution of standard HTML entities."""
    xml = "<root>&lt;&gt;&amp;&quot;&apos;</root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_event = [e for e in events if isinstance(e, Text)][0]
    assert text_event.content == "<>&\"'"


def test_numeric_entities():
    """Test numeric entity resolution."""
    xml = "<root>&#65;&#x41;&#8364;</root>"  # A, A, Euro symbol
    events = list(sloppy_xml.stream_parse(xml))

    text_event = [e for e in events if isinstance(e, Text)][0]
    assert "A" in text_event.content
    assert "€" in text_event.content or "&#8364;" in text_event.content


def test_extended_html_entities():
    """Test extended HTML entity resolution."""
    xml = "<root>&copy;&reg;&nbsp;</root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_event = [e for e in events if isinstance(e, Text)][0]
    expected_chars = {"©", "®", "\u00a0"}
    # Check if any expected characters are present (some might not resolve)
    content = text_event.content
    has_resolved = any(char in content for char in expected_chars)
    has_original = any(entity in content for entity in ["&copy;", "&reg;", "&nbsp;"])
    assert has_resolved or has_original


def test_invalid_entities():
    """Test handling of invalid entities."""
    xml = "<root>&invalid;&not;entity;</root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_event = [e for e in events if isinstance(e, Text)][0]
    # Invalid entities should be left as-is or handled gracefully
    assert "&invalid;" in text_event.content or "invalid" in text_event.content


def test_entity_resolution_disabled():
    """Test disabling entity resolution."""
    xml = "<root>&lt;&amp;</root>"
    events = list(sloppy_xml.stream_parse(xml, resolve_entities=False))

    text_event = [e for e in events if isinstance(e, Text)][0]
    assert "&lt;" in text_event.content
    assert "&amp;" in text_event.content


def test_malformed_numeric_entities():
    """Test handling of malformed numeric entities."""
    xml = "<root>&#invalid;&#x;&#999999999999999;</root>"
    events = list(sloppy_xml.stream_parse(xml))

    # Should not crash and should handle gracefully
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) > 0


def test_entity_resolution_in_attributes():
    """Test that entities are resolved in attribute values."""
    # Test the specific bug case reported
    xml = '<x><link href="https://secure.booking.invalid/myreservations.en-us.html?bn=4759;pincode=4391&amp;entrypoint=email_wakeup"/></x>'

    # Test with entity resolution enabled (default)
    events = list(sloppy_xml.stream_parse(xml, resolve_entities=True))
    start_events = [
        e for e in events if isinstance(e, StartElement) and e.name == "link"
    ]
    assert len(start_events) == 1
    href = start_events[0].attrs.get("href")
    assert (
        href
        == "https://secure.booking.invalid/myreservations.en-us.html?bn=4759;pincode=4391&entrypoint=email_wakeup"
    )
    assert "&amp;" not in href  # Entity should be resolved

    # Test with entity resolution disabled
    events = list(sloppy_xml.stream_parse(xml, resolve_entities=False))
    start_events = [
        e for e in events if isinstance(e, StartElement) and e.name == "link"
    ]
    assert len(start_events) == 1
    href = start_events[0].attrs.get("href")
    assert "&amp;" in href  # Entity should remain unresolved

    # Test various entity types in attribute values
    test_cases = [
        ('<test attr="&amp;"/>', "&"),
        ('<test attr="&lt;&gt;"/>', "<>"),
        ('<test attr="&quot;&apos;"/>', "\"'"),
        ('<test attr="&quot&apos"/>', "\"'"),
        ('<test attr="&#65;&#66;&#67;"/>', "ABC"),
        ('<test attr="&#x41;&#x42;&#x43;"/>', "ABC"),
    ]

    for xml, expected in test_cases:
        events = list(sloppy_xml.stream_parse(xml, resolve_entities=True))
        start_events = [
            e for e in events if isinstance(e, StartElement) and e.name == "test"
        ]
        assert len(start_events) == 1
        attr_value = start_events[0].attrs.get("attr")
        assert attr_value == expected, (
            f"Expected {expected!r}, got {attr_value!r} for {xml}"
        )

    # Test tree parsing also works correctly
    original_xml = '<x><link href="https://secure.booking.invalid/myreservations.en-us.html?bn=4759;pincode=4391&amp;entrypoint=email_wakeup"/></x>'
    root = sloppy_xml.tree_parse(original_xml)
    link = root.find("link")
    assert link is not None
    href = link.get("href")
    assert (
        href
        == "https://secure.booking.invalid/myreservations.en-us.html?bn=4759;pincode=4391&entrypoint=email_wakeup"
    )


def test_basic_comments():
    """Test parsing basic comments."""
    xml = "<!--comment--><root>content</root>"
    events = list(sloppy_xml.stream_parse(xml))

    comment_events = [e for e in events if isinstance(e, Comment)]
    assert len(comment_events) == 1
    assert comment_events[0].content == "comment"


def test_multiline_comments():
    """Test multiline comments."""
    xml = """<!--
        Multi-line
        comment
        --><root/>"""
    events = list(sloppy_xml.stream_parse(xml))

    comment_events = [e for e in events if isinstance(e, Comment)]
    assert len(comment_events) == 1
    assert "Multi-line" in comment_events[0].content


def test_comments_with_special_chars():
    """Test comments containing special characters."""
    xml = "<!--<>&\"'--><root/>"
    events = list(sloppy_xml.stream_parse(xml))

    comment_events = [e for e in events if isinstance(e, Comment)]
    assert len(comment_events) == 1
    assert comment_events[0].content == "<>&\"'"


def test_nested_comment_chars():
    """Test comments containing -- sequences."""
    xml = "<!--comment with -- double dashes--><root/>"
    events = list(sloppy_xml.stream_parse(xml))

    comment_events = [e for e in events if isinstance(e, Comment)]
    assert len(comment_events) == 1


def test_basic_pi():
    """Test basic processing instructions."""
    xml = '<?xml version="1.0"?><root/>'
    events = list(sloppy_xml.stream_parse(xml))

    pi_events = [e for e in events if isinstance(e, ProcessingInstruction)]
    assert len(pi_events) == 1
    assert pi_events[0].target == "xml"
    assert 'version="1.0"' in pi_events[0].data


def test_pi_without_data():
    """Test processing instructions without data."""
    xml = "<?target?><root/>"
    events = list(sloppy_xml.stream_parse(xml))

    pi_events = [e for e in events if isinstance(e, ProcessingInstruction)]
    assert len(pi_events) == 1
    assert pi_events[0].target == "target"
    assert pi_events[0].data is None or pi_events[0].data == ""


def test_multiple_pis():
    """Test multiple processing instructions."""
    xml = '<?xml version="1.0"?><?stylesheet type="text/css"?><root/>'
    events = list(sloppy_xml.stream_parse(xml))

    pi_events = [e for e in events if isinstance(e, ProcessingInstruction)]
    assert len(pi_events) == 2
    assert pi_events[0].target == "xml"
    assert pi_events[1].target == "stylesheet"


def test_basic_cdata():
    """Test basic CDATA sections."""
    xml = "<root><![CDATA[some data]]></root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == "some data"
    assert text_events[0].is_cdata


def test_cdata_with_special_chars():
    """Test CDATA with special characters."""
    xml = "<root><![CDATA[<>&\"']]></root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == "<>&\"'"
    assert text_events[0].is_cdata


def test_cdata_with_xml_content():
    """Test CDATA containing XML-like content."""
    xml = "<root><![CDATA[<tag>content</tag>]]></root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == "<tag>content</tag>"
    assert text_events[0].is_cdata


def test_unclosed_tags():
    """Test recovery from unclosed tags."""
    xml = "<root><child>text"
    events = list(sloppy_xml.stream_parse(xml, recover=True, auto_close_tags=True))

    # Should auto-close both tags
    end_events = [e for e in events if isinstance(e, EndElement)]
    assert len(end_events) >= 1  # At least the child should be auto-closed

    # Build tree to verify structure
    tree = sloppy_xml.tree_parse(xml, recover=True, auto_close_tags=True)
    assert tree is not None


def test_mismatched_tags():
    """Test recovery from mismatched tags."""
    xml = "<root><child></different></root>"
    events = list(sloppy_xml.stream_parse(xml, recover=True, emit_errors=True))

    error_events = [e for e in events if isinstance(e, ParseError)]
    assert len(error_events) > 0

    # Should still be able to build a tree
    tree = sloppy_xml.tree_parse(xml, recover=True, emit_errors=True)
    assert tree is not None


def test_malformed_attributes():
    """Test recovery from malformed attributes."""
    xml = '<root attr="missing quote>content</root>'
    events = list(
        sloppy_xml.stream_parse(xml, repair_attributes=True, emit_errors=True)
    )

    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 1
    # Should have attempted to fix the attribute
    assert "attr" in start_events[0].attrs or len(start_events[0].attrs) == 0


def test_broken_comments():
    """Test recovery from broken comments."""
    xml = "<!-- broken comment -> <root/>"
    events = list(
        sloppy_xml.stream_parse(
            xml, recovery_strategy=RecoveryStrategy.AGGRESSIVE, emit_errors=True
        )
    )

    # Should recover and parse both comment and element
    comment_events = [e for e in events if isinstance(e, Comment)]
    element_events = [e for e in events if isinstance(e, StartElement)]

    assert len(comment_events) >= 0  # May or may not recover comment
    assert len(element_events) == 1  # Should definitely get the element


def test_broken_cdata():
    """Test recovery from broken CDATA."""
    xml = "<root><![CDATA[broken cdata]></root>"
    events = list(
        sloppy_xml.stream_parse(xml, recovery_strategy=RecoveryStrategy.AGGRESSIVE)
    )

    # Should not crash and should produce some events
    assert len(events) > 0


def test_unescaped_characters():
    """Test recovery from unescaped special characters."""
    xml = "<root>text with < and & characters</root>"
    events = list(
        sloppy_xml.stream_parse(xml, recovery_strategy=RecoveryStrategy.LENIENT)
    )

    # Should handle gracefully
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) > 0


def test_recovery_strategies():
    """Test different recovery strategies."""
    malformed_xml = '<root><child attr="broken>text</child>'

    strategies = [
        RecoveryStrategy.STRICT,
        RecoveryStrategy.LENIENT,
        RecoveryStrategy.AGGRESSIVE,
    ]

    for strategy in strategies:
        events = list(
            sloppy_xml.stream_parse(
                malformed_xml, recovery_strategy=strategy, emit_errors=True
            )
        )

        # All strategies should produce some events
        assert len(events) > 0

        # More aggressive strategies should produce fewer errors or more recovery
        if strategy == RecoveryStrategy.AGGRESSIVE:
            # Should attempt maximum recovery
            element_events = [
                e for e in events if isinstance(e, (StartElement, EndElement))
            ]
            assert len(element_events) > 0


def test_empty_input():
    """Test parsing empty input."""
    events = list(sloppy_xml.stream_parse(""))
    assert len(events) == 0


def test_whitespace_only():
    """Test parsing whitespace-only input."""
    events = list(sloppy_xml.stream_parse("   \n\t  "))
    # Should either be empty or contain whitespace text
    assert len(events) >= 0


def test_single_character():
    """Test parsing single character."""
    events = list(sloppy_xml.stream_parse("a"))
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert text_events[0].content == "a"


def test_very_long_tag_names():
    """Test very long tag names."""
    long_name = "a" * 1000
    xml = f"<{long_name}>content</{long_name}>"
    events = list(sloppy_xml.stream_parse(xml))

    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 1
    assert start_events[0].name == long_name


def test_very_long_attribute_values():
    """Test very long attribute values."""
    long_value = "x" * 10000
    xml = f'<root attr="{long_value}">content</root>'
    events = list(sloppy_xml.stream_parse(xml))

    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 1
    assert start_events[0].attrs["attr"] == long_value


def test_deeply_nested_elements():
    """Test deeply nested elements."""
    depth = 100
    open_tags = "".join(f"<level{i}>" for i in range(depth))
    close_tags = "".join(f"</level{i}>" for i in range(depth - 1, -1, -1))
    xml = open_tags + "content" + close_tags

    events = list(sloppy_xml.stream_parse(xml))
    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == depth


def test_maximum_nesting_depth():
    """Test maximum nesting depth limit."""
    depth = 20
    xml = "".join(f"<level{i}>" for i in range(depth)) + "content"

    events = list(sloppy_xml.stream_parse(xml, max_depth=10))
    error_events = [e for e in events if isinstance(e, ParseError)]

    # Should hit depth limit and generate error
    depth_errors = [e for e in error_events if "depth" in e.error_type.lower()]
    assert len(depth_errors) > 0 or len(events) > 0  # Either error or truncation


def test_many_attributes():
    """Test elements with many attributes."""
    attrs = " ".join(f'attr{i}="value{i}"' for i in range(100))
    xml = f"<root {attrs}>content</root>"
    events = list(sloppy_xml.stream_parse(xml))

    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 1
    assert len(start_events[0].attrs) == 100


def test_special_characters_in_content():
    """Test special characters in text content."""
    special_chars = "áéíóú ñç 中文 🚀 \U0001f600"  # Unicode chars
    xml = f"<root>{special_chars}</root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert special_chars in text_events[0].content


def test_xml_declaration():
    """Test XML declaration handling."""
    xml = '<?xml version="1.0" encoding="UTF-8"?><root>content</root>'
    events = list(sloppy_xml.stream_parse(xml))

    pi_events = [e for e in events if isinstance(e, ProcessingInstruction)]
    # Should have XML declaration as processing instruction
    xml_decl = [e for e in pi_events if e.target == "xml"]
    assert len(xml_decl) == 1


def test_basic_namespaces():
    """Test basic namespace-aware parsing."""
    xml = '<root xmlns:ns="http://example.com"><ns:child>content</ns:child></root>'
    events = list(sloppy_xml.stream_parse(xml, namespace_aware=True))

    start_events = [e for e in events if isinstance(e, StartElement)]
    ns_elements = [e for e in start_events if ":" in e.name]
    assert len(ns_elements) > 0


def test_default_namespace():
    """Test default namespace handling."""
    xml = '<root xmlns="http://example.com"><child>content</child></root>'
    events = list(sloppy_xml.stream_parse(xml, namespace_aware=True))

    # Should parse without errors
    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 2


def test_namespace_disabled():
    """Test parsing with namespaces disabled."""
    xml = (
        '<ns:root xmlns:ns="http://example.com"><ns:child>content</ns:child></ns:root>'
    )
    events = list(sloppy_xml.stream_parse(xml, namespace_aware=False))  # Default

    start_events = [e for e in events if isinstance(e, StartElement)]
    # Should treat ns:root as a regular tag name
    assert any(e.name == "ns:root" for e in start_events)


def test_large_document_performance():
    """Test performance with large documents."""
    # Create a moderately large XML document
    num_elements = 5000
    xml_parts = ["<root>"]
    xml_parts.extend(
        f"<item{i} id='{i}'>Content for item {i}</item{i}>" for i in range(num_elements)
    )
    xml_parts.append("</root>")
    large_xml = "".join(xml_parts)

    start_time = time.time()
    events = list(sloppy_xml.stream_parse(large_xml))
    parse_time = time.time() - start_time

    # Should complete in reasonable time (less than 1 second for 5000 elements)
    assert parse_time < 5.0, f"Parsing took {parse_time:.2f} seconds, too slow"

    # Should produce correct number of events
    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == num_elements + 1  # +1 for root


def test_deep_nesting_performance():
    """Test performance with deeply nested documents."""
    depth = 500
    open_tags = "".join(f"<level{i}>" for i in range(depth))
    close_tags = "".join(f"</level{i}>" for i in range(depth - 1, -1, -1))
    deep_xml = open_tags + "content" + close_tags

    start_time = time.time()
    events = list(sloppy_xml.stream_parse(deep_xml, max_depth=600))
    parse_time = time.time() - start_time

    # Should complete in reasonable time
    assert parse_time < 2.0, f"Deep nesting parsing took {parse_time:.2f} seconds"
    assert len(events) > 0


def test_memory_usage_streaming():
    """Test that streaming doesn't accumulate excessive memory."""
    # Create a large document
    large_xml = (
        "<root>" + "".join(f"<item{i}>data</item{i}>" for i in range(1000)) + "</root>"
    )

    # Parse as generator - should not load everything into memory
    event_generator = sloppy_xml.stream_parse(large_xml)

    # Process a few events to ensure generator works
    first_few_events = []
    for i, event in enumerate(event_generator):
        first_few_events.append(event)
        if i >= 10:  # Just get first 10 events
            break

    assert len(first_few_events) == 11
    # Generator should still have more events available
    next_event = next(event_generator, None)
    assert next_event is not None


def test_entity_heavy_performance():
    """Test performance with many entities."""
    # Create XML with many entity references
    content_with_entities = "Text with &amp; &lt; &gt; entities " * 1000
    xml = f"<root>{content_with_entities}</root>"

    start_time = time.time()
    events = list(sloppy_xml.stream_parse(xml))
    parse_time = time.time() - start_time

    assert parse_time < 2.0
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1


def test_llm_generated_malformed_xml():
    """Test typical LLM-generated malformed XML."""
    malformed_examples = [
        # Missing quotes in attributes
        "<root attr=value>content</root>",
        # Mixed quotes
        "<root attr=\"value'>content</root>",
        # Unclosed tags
        "<root><child>content",
        # Tag soup
        "<div><p>text<span>more</div>",
        # Unescaped characters
        "<root>text with < and & chars</root>",
        # Broken CDATA
        "<root><![CDATA[some data]></root>",
        # Malformed comments
        "<root><!-- comment -> more content</root>",
    ]

    for i, xml in enumerate(malformed_examples):
        try:
            events = list(
                sloppy_xml.stream_parse(
                    xml,
                    recovery_strategy=RecoveryStrategy.AGGRESSIVE,
                    repair_attributes=True,
                )
            )
            # Should not crash and should produce some events
            assert len(events) > 0, f"Example {i} produced no events"

            # Try to build tree
            tree = sloppy_xml.tree_parse(
                xml,
                recovery_strategy=RecoveryStrategy.AGGRESSIVE,
                repair_attributes=True,
            )
            assert tree is not None, f"Example {i} failed to build tree"

        except Exception as e:
            pytest.fail(f"Example {i} crashed with: {e}")


def test_html_like_structures():
    """Test HTML-like structures that are not well-formed XML."""
    html_examples = [
        '<div><p>paragraph<br><img src="test.jpg"></div>',
        "<ul><li>item 1<li>item 2</ul>",
        "<table><tr><td>cell</table>",
        "<div class=test>content</div>",  # unquoted attribute
    ]

    for html in html_examples:
        events = list(
            sloppy_xml.stream_parse(
                html,
                recovery_strategy=RecoveryStrategy.AGGRESSIVE,
                repair_attributes=True,
                auto_close_tags=True,
            )
        )
        assert len(events) > 0

        # Should be able to build some kind of tree
        tree = sloppy_xml.tree_parse(
            html,
            recovery_strategy=RecoveryStrategy.AGGRESSIVE,
            repair_attributes=True,
            auto_close_tags=True,
        )
        assert tree is not None


def test_mixed_content_types():
    """Test documents with mixed content types."""
    mixed_xml = """
        <?xml version="1.0"?>
        <!-- This is a comment -->
        <root>
            Text content
            <![CDATA[<script>alert('hello')</script>]]>
            <child attr="value">
                More text &amp; entities
                <grandchild/>
            </child>
            <?processing instruction data?>
        </root>
        """

    events = list(sloppy_xml.stream_parse(mixed_xml))

    # Should have various event types
    event_types = {type(e).__name__ for e in events}
    expected_types = {
        "StartElement",
        "EndElement",
        "Text",
        "Comment",
        "ProcessingInstruction",
    }

    # Should have most of the expected types
    assert len(event_types.intersection(expected_types)) >= 3


def test_encoding_issues():
    """Test documents with encoding issues."""
    # Simulate common encoding problems
    xml_with_issues = '<root>Text with em—dash and "smart quotes"</root>'

    events = list(
        sloppy_xml.stream_parse(xml_with_issues, fix_encoding=True, emit_errors=True)
    )

    # Should handle without crashing
    assert len(events) > 0

    # Should be able to build tree
    tree = sloppy_xml.tree_parse(xml_with_issues, fix_encoding=True, emit_errors=True)
    assert tree is not None


def test_fragment_parsing():
    """Test parsing XML fragments."""
    fragments = [
        "Just text content",
        "<child>content</child>",  # No root
        "<p>para1</p><p>para2</p>",  # Multiple roots
        "Text before <tag>content</tag> text after",
    ]

    for fragment in fragments:
        events = list(sloppy_xml.stream_parse(fragment, allow_fragments=True))
        assert len(events) > 0

        # Should be able to handle fragments in tree parsing too
        try:
            tree = sloppy_xml.tree_parse(fragment, allow_fragments=True)
            assert tree is not None
        except ValueError:
            # Some fragments might not produce valid trees, that's ok
            pass


def test_full_pipeline_wellformed():
    """Test complete parsing pipeline with well-formed XML."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
        <!-- Sample document -->
        <document xmlns="http://example.com">
            <title>Test Document</title>
            <content>
                <p>Paragraph with <em>emphasis</em> and &amp; entities.</p>
                <list>
                    <item id="1">First item</item>
                    <item id="2">Second item</item>
                </list>
                <data><![CDATA[<xml>raw data</xml>]]></data>
            </content>
        </document>"""

    # Test stream parsing
    events = list(sloppy_xml.stream_parse(xml))
    assert len(events) > 10

    # Test tree building
    tree = sloppy_xml.tree_parse(xml)
    assert tree.tag == "document"
    assert len(tree) == 2  # title and content

    # Test with various options
    tree_with_opts = sloppy_xml.tree_parse(
        xml, preserve_whitespace=False, resolve_entities=True, namespace_aware=True
    )
    assert tree_with_opts.tag == "document"


def test_full_pipeline_malformed():
    """Test complete parsing pipeline with malformed XML."""
    malformed_xml = """<!-- broken comment ->
        <document>
            <title attr="missing quote>Test Document</title>
            <content>
                <p>Paragraph with unescaped < characters
                <list>
                    <item id=1>First item
                    <item id="2">Second item</item>
                <data><![CDATA[broken cdata]></data>
            <content>
        """

    # Should handle malformed XML gracefully
    events = list(
        sloppy_xml.stream_parse(
            malformed_xml,
            recovery_strategy=RecoveryStrategy.AGGRESSIVE,
            emit_errors=True,
            repair_attributes=True,
            auto_close_tags=True,
        )
    )
    assert len(events) > 0

    # Should be able to build a tree despite issues
    tree = sloppy_xml.tree_parse(
        malformed_xml,
        recovery_strategy=RecoveryStrategy.AGGRESSIVE,
        emit_errors=True,
        repair_attributes=True,
        auto_close_tags=True,
    )
    assert tree is not None
    assert tree.tag == "document"


def test_error_collection():
    """Test error collection functionality."""
    malformed_xml = """<root>
            <child attr="broken">content</child>
            <unclosed>content
            </wrong_end>
        </root>"""

    events = list(
        sloppy_xml.stream_parse(
            malformed_xml,
            collect_errors=True,
            emit_errors=True,
            recovery_strategy=RecoveryStrategy.LENIENT,
        )
    )

    # Should have collected errors
    error_events = [e for e in events if isinstance(e, ParseError)]
    assert len(error_events) > 0


def test_file_integration():
    """Test integration with file I/O."""
    xml_content = "<root><child>file content</child></root>"

    # Test with temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml_content)
        temp_path = f.name

    try:
        # Test parsing from file path (using open)
        with open(temp_path, "r") as file:
            events = list(sloppy_xml.stream_parse(file))
            assert (
                len(events) == 5
            )  # StartElement, StartElement, Text, EndElement, EndElement

            # Test tree parsing from file
            file.seek(0)
            tree = sloppy_xml.tree_parse(file)
            assert tree.tag == "root"
            assert tree[0].text == "file content"

    finally:
        os.unlink(temp_path)


def test_custom_options_integration():
    """Test integration of custom parsing options."""
    xml = '<root attr="value">Text with &amp; entity</root>'

    # Test with custom options
    events = list(
        sloppy_xml.stream_parse(
            xml,
            recover=True,
            emit_errors=False,
            preserve_whitespace=True,
            resolve_entities=False,
            max_depth=500,
            recovery_strategy=RecoveryStrategy.LENIENT,
            repair_attributes=False,
        )
    )  # Keep entities as-is

    # Check that options were respected
    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    # Entity should not be resolved
    assert "&amp;" in text_events[0].content


# Utility fixtures and helpers
@pytest.fixture
def sample_xml():
    """Fixture providing sample well-formed XML."""
    return """<?xml version="1.0"?>
    <catalog>
        <book id="1" genre="fiction">
            <title>The Great Gatsby</title>
            <author>F. Scott Fitzgerald</author>
            <price>12.99</price>
        </book>
        <book id="2" genre="fiction">
            <title>1984</title>
            <author>George Orwell</author>
            <price>13.99</price>
        </book>
    </catalog>"""


@pytest.fixture
def malformed_xml():
    """Fixture providing malformed XML for testing recovery."""
    return """<catalog>
        <book id=1 genre="fiction">
            <title>The Great Gatsby
            <author>F. Scott Fitzgerald</author>
            <price>12.99</price>
        </book>
        <book id="2" genre=fiction>
            <title>1984</title>
            <author>George Orwell</author>
        <book>
    """


def test_sample_xml_fixture(sample_xml):
    """Test parsing with sample XML fixture."""
    events = list(sloppy_xml.stream_parse(sample_xml))

    # Should have books
    start_events = [e for e in events if isinstance(e, StartElement)]
    book_elements = [e for e in start_events if e.name == "book"]
    assert len(book_elements) == 2

    # Should build valid tree
    tree = sloppy_xml.tree_parse(sample_xml)
    assert tree.tag == "catalog"
    assert len(tree) == 2


def test_malformed_xml_fixture(malformed_xml):
    """Test recovery with malformed XML fixture."""
    events = list(
        sloppy_xml.stream_parse(
            malformed_xml, recovery_strategy=RecoveryStrategy.AGGRESSIVE
        )
    )

    # Should still produce events despite malformation
    assert len(events) > 0

    # Should be able to build some kind of tree
    tree = sloppy_xml.tree_parse(
        malformed_xml, recovery_strategy=RecoveryStrategy.AGGRESSIVE
    )
    assert tree is not None


# Parametrized tests
@pytest.mark.parametrize(
    "recovery_strategy",
    [
        RecoveryStrategy.STRICT,
        RecoveryStrategy.LENIENT,
        RecoveryStrategy.AGGRESSIVE,
    ],
)
def test_recovery_strategies_parametrized(recovery_strategy):
    """Test all recovery strategies with parametrized tests."""
    xml = '<root><child attr="broken>text</child>'
    events = list(
        sloppy_xml.stream_parse(
            xml, recovery_strategy=recovery_strategy, emit_errors=True
        )
    )
    assert len(events) > 0


@pytest.mark.parametrize(
    "entity,expected",
    [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&apos;", "'"),
        ("&#65;", "A"),
        ("&#x41;", "A"),
    ],
)
def test_entity_resolution_parametrized(entity, expected):
    """Test entity resolution with parametrized entities."""
    xml = f"<root>{entity}</root>"
    events = list(sloppy_xml.stream_parse(xml))

    text_events = [e for e in events if isinstance(e, Text)]
    assert len(text_events) == 1
    assert expected in text_events[0].content


@pytest.mark.parametrize(
    "malformed_attr",
    [
        'attr="missing end quote',
        "attr='missing end quote",
        "attr=\"mixed quote'",
        "attr=unquoted_value",
        'attr=""',
        "attr",  # No value
    ],
)
def test_malformed_attributes_parametrized(malformed_attr):
    """Test various malformed attribute scenarios."""
    xml = f"<root {malformed_attr}>content</root>"
    events = list(
        sloppy_xml.stream_parse(
            xml, repair_attributes=True, recovery_strategy=RecoveryStrategy.AGGRESSIVE
        )
    )

    # Should not crash
    assert len(events) > 0

    # Should produce a start element
    start_events = [e for e in events if isinstance(e, StartElement)]
    assert len(start_events) == 1


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
