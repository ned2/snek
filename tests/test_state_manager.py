"""Tests for state management."""
import pytest
from snek.state_manager import StateManager
from snek.constants import GameState


class TestStateManager:
    """Test StateManager class."""
    
    def test_initialization(self):
        """Test state manager initialization."""
        manager = StateManager()
        assert manager.current_state == GameState.SPLASH
        assert manager.previous_state is None
    
    def test_transition_to(self):
        """Test state transitions."""
        manager = StateManager()
        
        # Transition to playing
        manager.transition_to(GameState.PLAYING)
        assert manager.current_state == GameState.PLAYING
        assert manager.previous_state == GameState.SPLASH
        
        # Transition to paused
        manager.transition_to(GameState.PAUSED)
        assert manager.current_state == GameState.PAUSED
        assert manager.previous_state == GameState.PLAYING
    
    def test_is_state(self):
        """Test state checking."""
        manager = StateManager()
        assert manager.is_state(GameState.SPLASH)
        assert not manager.is_state(GameState.PLAYING)
        
        manager.transition_to(GameState.PLAYING)
        assert manager.is_state(GameState.PLAYING)
        assert not manager.is_state(GameState.SPLASH)
    
    def test_can_transition_to(self):
        """Test transition validation."""
        manager = StateManager()
        
        # From splash
        assert manager.can_transition_to(GameState.PLAYING)
        assert not manager.can_transition_to(GameState.PAUSED)
        assert not manager.can_transition_to(GameState.GAME_OVER)
        
        # From playing
        manager.transition_to(GameState.PLAYING)
        assert manager.can_transition_to(GameState.PAUSED)
        assert manager.can_transition_to(GameState.GAME_OVER)
        assert not manager.can_transition_to(GameState.SPLASH)
    
    def test_callbacks(self):
        """Test state entry callbacks."""
        manager = StateManager()
        callback_called = False
        callback_state = None
        
        def test_callback():
            nonlocal callback_called, callback_state
            callback_called = True
            callback_state = manager.current_state
        
        # Register callback
        manager.register_callback(GameState.PLAYING, test_callback)
        
        # Transition should trigger callback
        manager.transition_to(GameState.PLAYING)
        assert callback_called
        assert callback_state == GameState.PLAYING
