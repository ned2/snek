"""Game state management for Snek."""

from typing import Callable
from snek.constants import GameState


class StateManager:
    """Manages game state transitions."""

    def __init__(self):
        self.current_state = GameState.SPLASH
        self.previous_state = None
        self.state_callbacks: dict[str, Callable] = {}

    def register_callback(self, state: str, callback: Callable) -> None:
        """Register a callback for state entry."""
        self.state_callbacks[state] = callback

    def transition_to(self, new_state: str) -> None:
        """Transition to a new state."""
        if self.current_state == new_state:
            return

        self.previous_state = self.current_state
        self.current_state = new_state

        # Call state entry callback if registered
        if new_state in self.state_callbacks:
            self.state_callbacks[new_state]()

    def is_state(self, state: str) -> bool:
        """Check if currently in a specific state."""
        return self.current_state == state

    def can_transition_to(self, target_state: str) -> bool:
        """Check if transition to target state is valid."""
        valid_transitions = {
            GameState.SPLASH: [GameState.PLAYING],
            GameState.PLAYING: [GameState.PAUSED, GameState.GAME_OVER],
            GameState.PAUSED: [GameState.PLAYING, GameState.SPLASH],
            GameState.GAME_OVER: [GameState.SPLASH, GameState.PLAYING],
        }

        return target_state in valid_transitions.get(self.current_state, [])
