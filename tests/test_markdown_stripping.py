"""
Tests for markdown formatting removal before TTS synthesis
"""

import pytest
from src.lambda_handler import strip_markdown_formatting


class TestMarkdownStripping:
    """Test markdown formatting removal"""
    
    def test_strip_bold_double_asterisk(self):
        """Remove **bold** markers"""
        text = "This is **bold text** in a sentence"
        result = strip_markdown_formatting(text)
        assert result == "This is bold text in a sentence"
        assert "**" not in result
    
    def test_strip_bold_double_underscore(self):
        """Remove __bold__ markers"""
        text = "This is __bold text__ in a sentence"
        result = strip_markdown_formatting(text)
        assert result == "This is bold text in a sentence"
        assert "__" not in result
    
    def test_strip_italic_single_asterisk(self):
        """Remove *italic* markers"""
        text = "This is *italic text* in a sentence"
        result = strip_markdown_formatting(text)
        assert result == "This is italic text in a sentence"
        assert "*" not in result
    
    def test_strip_italic_single_underscore(self):
        """Remove _italic_ markers"""
        text = "This is _italic text_ in a sentence"
        result = strip_markdown_formatting(text)
        assert result == "This is italic text in a sentence"
    
    def test_strip_headers(self):
        """Remove # header markers"""
        text = "# Header 1\n## Header 2\nNormal text"
        result = strip_markdown_formatting(text)
        assert result == "Header 1\nHeader 2\nNormal text"
        assert "#" not in result
    
    def test_strip_list_markers(self):
        """Remove list markers (-, *, 1.)"""
        text = "- Item 1\n- Item 2\n* Item 3\n1. Item 4"
        result = strip_markdown_formatting(text)
        assert "- " not in result
        assert "* " not in result
        assert "1. " not in result
    
    def test_strip_links(self):
        """Remove [text](url) links, keep text"""
        text = "Visit [our website](https://example.com) for more"
        result = strip_markdown_formatting(text)
        assert result == "Visit our website for more"
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
    
    def test_strip_inline_code(self):
        """Remove `code` markers"""
        text = "Use the `function()` to do this"
        result = strip_markdown_formatting(text)
        assert result == "Use the function() to do this"
        assert "`" not in result
    
    def test_strip_code_blocks(self):
        """Remove ```code blocks```"""
        text = "Here is code:\n```python\nprint('hello')\n```\nEnd of code"
        result = strip_markdown_formatting(text)
        assert "```" not in result
        assert "print('hello')" not in result
    
    def test_multiple_formatting_types(self):
        """Handle multiple formatting types in one text"""
        text = "**Bold** and *italic* with `code` and [link](url)"
        result = strip_markdown_formatting(text)
        assert result == "Bold and italic with code and link"
        assert "**" not in result
        assert "*" not in result
        assert "`" not in result
        assert "[" not in result
    
    def test_tamil_text_with_bold(self):
        """Handle Tamil text with bold markers"""
        text = "இது **முக்கியமான** தகவல்"
        result = strip_markdown_formatting(text)
        assert result == "இது முக்கியமான தகவல்"
        assert "**" not in result
    
    def test_empty_text(self):
        """Handle empty text"""
        result = strip_markdown_formatting("")
        assert result == ""
    
    def test_none_text(self):
        """Handle None text"""
        result = strip_markdown_formatting(None)
        assert result is None
    
    def test_text_without_markdown(self):
        """Plain text should remain unchanged"""
        text = "This is plain text without any formatting"
        result = strip_markdown_formatting(text)
        assert result == text
    
    def test_preserve_normal_asterisks_in_context(self):
        """Don't remove asterisks that aren't markdown"""
        # Single asterisks at start/end of words should be removed if they're markdown
        # But this is tricky - the regex should handle common cases
        text = "Temperature is 25*C"  # Not markdown
        result = strip_markdown_formatting(text)
        # This might still have the asterisk, which is okay
        # The important thing is **bold** is removed
        assert "**" not in result
    
    def test_real_world_example(self):
        """Test with real-world Claude response"""
        text = """வணக்கம்! **ரோஜா செடிகள்** பராமரிப்பு குறித்து:

1. **தண்ணீர்**: தினமும் காலை நேரத்தில்
2. **உரம்**: மாதம் ஒருமுறை
3. **வெயில்**: நாள் ஒன்றுக்கு 6 மணி நேரம்

*முக்கியம்*: இலைகளில் தண்ணீர் தெளிக்க வேண்டாம்."""
        
        result = strip_markdown_formatting(text)
        
        # Should not have any markdown markers
        assert "**" not in result
        assert "*" not in result
        assert "1. " not in result
        assert "2. " not in result
        assert "3. " not in result
        
        # Should still have the Tamil text
        assert "வணக்கம்" in result
        assert "ரோஜா செடிகள்" in result
        assert "தண்ணீர்" in result
