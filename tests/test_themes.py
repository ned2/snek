"""Tests for theme management."""
import pytest
from snek.themes import Theme, ThemeManager


class TestTheme:
    """Test Theme class."""
    
    def test_theme_creation(self):
        """Test creating a theme."""
        theme = Theme(
            name="Test",
            primary_color="green"
        )
        
        assert theme.name == "Test"
        assert theme.primary_color == "green"
        assert theme.css_color == "green"


class TestThemeManager:
    """Test ThemeManager class."""
    
    def test_initialization(self):
        """Test theme manager initialization."""
        manager = ThemeManager()
        assert len(manager.themes) > 0
        assert manager.current_theme_index == 0
    
    def test_get_theme_for_level(self):
        """Test getting theme by level."""
        manager = ThemeManager()
        
        # Should cycle through themes
        theme1 = manager.get_theme_for_level(1)
        theme2 = manager.get_theme_for_level(2)
        assert theme1.name != theme2.name
        
        # Should wrap around
        total_themes = len(manager.themes)
        theme_wrap = manager.get_theme_for_level(total_themes + 1)
        assert theme_wrap.name == theme1.name
    
    def test_set_level(self):
        """Test setting theme by level."""
        manager = ThemeManager()
        
        # Set to level 2
        theme = manager.set_level(2)
        assert manager.current_theme_index == 1
        assert theme == manager.themes[1]
        
        # Current theme should match
        assert manager.get_current_theme() == theme
