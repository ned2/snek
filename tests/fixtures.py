"""Shared test fixtures and utilities."""

import random

import pytest

from snek.game import Game


@pytest.fixture
def small_game() -> Game:
    """Provide a small game for testing."""
    return Game(width=5, height=5)


@pytest.fixture
def seeded_game() -> Game:
    """Provide a game with seeded randomness."""
    rng = random.Random(42)
    return Game(width=10, height=10, rng=rng)


class GameTestHelper:
    """Helper methods for game testing."""

    @staticmethod
    def move_snake_to(game: Game, positions: list[tuple[int, int]]) -> None:
        """Move snake to specific positions."""
        game.snake = positions

    @staticmethod
    def place_food_at(game: Game, x: int, y: int) -> None:
        """Place food at specific position."""
        game.food = (x, y)

    @staticmethod
    def make_snake_long(game: Game, length: int) -> None:
        """Make snake a specific length."""
        head = game.snake[0]
        game.snake = [(head[0] - i, head[1]) for i in range(length)]

    @staticmethod
    def simulate_game_over(game: Game) -> None:
        """Put game in game over state."""
        game.game_over = True
