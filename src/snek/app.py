from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Static
from textual_pyfiglet import FigletWidget

from .config import GameConfig, default_config
from .game import Game
from .game_rules import Direction
from .themes import ThemeManager
from .state_manager import StateManager
from .constants import (
    GameState, STATS_PANEL_WIDTH, MIN_GAME_WIDTH, MIN_GAME_HEIGHT,
    SNEK_TITLE, SNEK_ASCII_ART, KEY_BINDINGS
)

class SplashView(Vertical):
    can_focus = True
    """Splash screen with retro arcade vibes."""
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        # Start with opacity 0 for fade-in effect
        self.styles.opacity = 0.0
        
    def on_mount(self) -> None:
        """Animate fade-in when the splash screen is mounted."""
        self.styles.animate("opacity", value=1.0, duration=2.0)
        # Update figlet color based on theme
        theme = self.theme_manager.get_current_theme()
        figlet = self.query_one("#splash-title", FigletWidget)
        figlet.styles.color = theme.css_color
    
    def compose(self) -> ComposeResult:
        """Compose the splash screen with FigletWidget."""
        with Vertical(id="splash-container"):
            yield FigletWidget("SNEK", font="slant", id="splash-title")
            yield Static("")  # Empty line for spacing
            yield Static("Press any key to start", classes="splash-prompt")
            yield Static("Use arrow keys to move, P to pause, Q to quit", classes="splash-controls")

    async def on_key(self, event: events.Key) -> None:
        """Start game on any key press, or quit on Q."""
        if event.key.upper() == "Q":
            await self.app.action_quit()
        else:
            self.app.start_game()
        event.stop()

class DeathView(Vertical):
    can_focus = True
    """Splash screen shown when snek dies."""
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        
    def compose(self) -> ComposeResult:
        """Compose the death screen with FigletWidget."""
        with Vertical(id="death-container"):
            yield FigletWidget("GAME OVER", font="doom", id="death-title")
            yield Static("")  # Empty line for spacing
            yield Static("💀 SNEK DIED! 💀", classes="death-message")
            yield Static("Press Q to quit or any other key to restart", classes="death-prompt")

class PauseView(Vertical):
    can_focus = True
    """Splash screen shown when game is paused."""
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        
    def on_mount(self) -> None:
        """Update figlet color based on theme when mounted."""
        theme = self.theme_manager.get_current_theme()
        figlet = self.query_one("#pause-title", FigletWidget)
        figlet.styles.color = theme.css_color
        
    def compose(self) -> ComposeResult:
        """Compose the pause screen with FigletWidget."""
        with Vertical(id="pause-container"):
            yield FigletWidget("PAUSED", font="banner", id="pause-title")
            yield Static("")  # Empty line for spacing
            yield Static("Press any key to continue", classes="pause-prompt")

class SnakeView(Static):
    """Renders the game as text."""
    def __init__(self, game: Game, theme_manager: ThemeManager, config: GameConfig = None) -> None:
        super().__init__()
        self.game = game
        self.theme_manager = theme_manager
        self.config = config or default_config

    def render(self) -> Text:
        """Render the game grid using solid block symbols for the snake."""
        width, height = self.game.width, self.game.height
        grid = [[self.config.empty_cell for _ in range(width)] for _ in range(height)]
        snake = self.game.snake

        # Create the rendered text
        text = Text()

        for y in range(height):
            for x in range(width):
                if (x, y) in snake:
                    # Snake uses theme color
                    theme = self.theme_manager.get_current_theme()
                    text.append(self.config.snake_block, style=theme.css_color)
                elif (x, y) == self.game.food:
                    # Food uses theme color
                    theme = self.theme_manager.get_current_theme()
                    text.append(f"{self.game.food_emoji} ", style=theme.css_color)
                else:
                    text.append(self.config.empty_cell)
            if y < height - 1:  # Don't add newline after last row
                text.append("\n")

        if self.game.game_over:
            text.append("\n\n GAME OVER! Press R to restart.")
        
        return text

class AsciiArtPanel(Static):
    """Panel for ASCII art at bottom of stats."""
    def __init__(self, game: Game, theme_manager: ThemeManager) -> None:
        super().__init__(id="ascii-art")
        self.game = game
        self.theme_manager = theme_manager

    def render(self) -> Text:
        """Render the ASCII art."""
        theme = self.theme_manager.get_current_theme()
        return Text(SNEK_ASCII_ART, style=f"bold {theme.css_color}", justify="center")

class StatsPanel(Static):
    """Panel showing game statistics."""
    def __init__(self, game: Game, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.game = game
        self.theme_manager = theme_manager
        self._last_theme = theme_manager.get_current_theme()

    def compose(self) -> ComposeResult:
        """Compose the stats panel with ASCII art at bottom."""
        yield Vertical(
            Static(id="stats-content"),
            AsciiArtPanel(self.game, self.theme_manager),
            id="stats-container"
        )

    def on_mount(self) -> None:
        """Update content when mounted."""
        self.update_content()

    def update_content(self) -> None:
        """Update the stats content and colors."""
        theme = self.theme_manager.get_current_theme()
        
        # Check if theme changed and update border if needed
        if self._last_theme != theme:
            self._last_theme = theme
            self.styles.border = ("solid", theme.css_color)
        
        # Get current world info
        world_name = self.game.world_path.get_world_name(self.game.level)
        
        stats_text = Text()
        stats_text.append(f"Level: {self.game.level}\n", style=theme.css_color)
        stats_text.append(f"World: {world_name}\n", style=theme.css_color)
        stats_text.append(f"Symbols: {self.game.symbols_consumed}\n", style=theme.css_color)
        stats_text.append(f"Length: {len(self.game.snake)}\n", style=theme.css_color)
        stats_text.append(f"Speed: {self.game.get_moves_per_second():.1f}/sec\n\n", style=theme.css_color)
        
        # Update the stats content
        stats_content = self.query_one("#stats-content", Static)
        stats_content.update(stats_text)
        
        # Update ASCII art color
        ascii_art = self.query_one("#ascii-art", AsciiArtPanel)
        ascii_art.refresh()

class SnakeApp(App):
    def __init__(self, config: GameConfig = None, css_path: str = "styles.css", **kwargs) -> None:
        self.CSS_PATH = css_path
        super().__init__(**kwargs)
        self.config = config or default_config
        self.theme_manager = ThemeManager()
        self.state_manager = StateManager()
        self.splash_view: SplashView | None = None
        self.game: Game | None = None
        self.view_widget: SnakeView | None = None
        self.stats_widget: StatsPanel | None = None
        self.game_container: Horizontal | None = None
        self.timer: Timer | None = None
        self.interval: float | None = None
        self.death_view: DeathView | None = None
        self.pause_view: PauseView | None = None
        
        # Register state callbacks
        self._register_state_callbacks()

    def _register_state_callbacks(self) -> None:
        """Register callbacks for state transitions."""
        self.state_manager.register_callback(GameState.PLAYING, self._on_playing_state)
        self.state_manager.register_callback(GameState.PAUSED, self._on_paused_state)
        self.state_manager.register_callback(GameState.GAME_OVER, self._on_game_over_state)
    
    def _on_playing_state(self) -> None:
        """Handle transition to playing state."""
        pass
    
    def _on_paused_state(self) -> None:
        """Handle transition to paused state."""
        pass
    
    def _on_game_over_state(self) -> None:
        """Handle transition to game over state."""
        pass
    
    def compose(self) -> ComposeResult:
        if self.state_manager.is_state(GameState.SPLASH):
            self.splash_view = SplashView(self.theme_manager)
            yield self.splash_view
        else:
            self.view_widget = SnakeView(self.game, self.theme_manager)
            yield Horizontal(
                self.view_widget,
                StatsPanel(self.game, self.theme_manager)
            )

    def _clear_all_widgets(self) -> None:
        """Clear all game-related widgets."""
        if self.splash_view:
            self.splash_view.remove()
            self.splash_view = None
        if self.death_view:
            self.death_view.remove()
            self.death_view = None
        if self.pause_view:
            self.pause_view.remove()
            self.pause_view = None
        if self.game_container:
            self.game_container.remove()
            self.game_container = None
        self.view_widget = None
        self.stats_widget = None

    def _calculate_game_dimensions(self, terminal_width: int, terminal_height: int) -> tuple[int, int]:
        """Calculate game dimensions from terminal size."""
        game_width = max(MIN_GAME_WIDTH, (terminal_width - STATS_PANEL_WIDTH) // 2)
        game_height = max(MIN_GAME_HEIGHT, terminal_height)
        return game_width, game_height
    
    def start_game(self) -> None:
        """Transition from splash screen to game."""
        self.state_manager.transition_to(GameState.PLAYING)
        
        # Clear any existing widgets
        self._clear_all_widgets()
            
        width, height = self.size
        game_width, game_height = self._calculate_game_dimensions(width, height)
        
        self.game = Game(width=game_width, height=game_height, config=self.config)
        self.view_widget = SnakeView(self.game, self.theme_manager, self.config)
        self.stats_widget = StatsPanel(self.game, self.theme_manager)
        
        # Create layout: game and stats side by side
        self.game_container = Horizontal(
            self.view_widget,
            self.stats_widget,
            id="game-content"
        )
        
        self.mount(self.game_container)
        self.interval = self.config.initial_speed_interval
        self.timer = self.set_interval(self.interval, self.tick)
        self._timer_started = True  # For testing

    def tick(self) -> None:
        pre_length = len(self.game.snake)
        old_level = self.game.level
        
        self.game.step()
        
        # Update theme if level changed
        if self.game.level != old_level:
            self.theme_manager.set_level(self.game.level)
            self.stats_widget.update_content()
        
        if self.game.game_over:
            self.show_death()
            return
            
        if len(self.game.snake) > pre_length:
            # Snake ate food, increase speed
            self.interval *= self.config.speed_increase_factor
            # Stop the old timer
            if self.timer:
                self.timer.stop()
            # Create a new timer with the updated interval
            self.timer = self.set_interval(self.interval, self.tick)
            # Update game's speed tracking
            self.game.update_speed(self.interval)
        
        self.view_widget.refresh()
        self.stats_widget.update_content()

    def show_death(self) -> None:
        """Show death splash and wait for restart."""
        self.state_manager.transition_to(GameState.GAME_OVER)
        
        if self.timer:
            self.timer.stop()
            self.timer = None
            
        # Clear game widgets
        self._clear_all_widgets()
        
        # Show death screen
        self.death_view = DeathView(self.theme_manager)
        self.mount(self.death_view)
        self.death_view.focus()

    def pause_game(self) -> None:
        """Pause the game and show pause screen."""
        if not self.game or self.game.game_over or self.game.paused:
            return
            
        self.game.paused = True
        self.state_manager.transition_to(GameState.PAUSED)
        
        # Stop the timer
        if self.timer:
            self.timer.stop()
            
        # Clear game widgets but keep references for unpausing
        if self.game_container:
            self.game_container.remove()
            
        # Show pause screen
        self.pause_view = PauseView(self.theme_manager)
        self.mount(self.pause_view)
        self.pause_view.focus()

    def unpause_game(self) -> None:
        """Unpause the game and restore game view."""
        if not self.game or not self.game.paused:
            return
            
        self.game.paused = False
        self.state_manager.transition_to(GameState.PLAYING)
        
        # Remove pause screen
        if self.pause_view:
            self.pause_view.remove()
            self.pause_view = None
            
        # Recreate game widgets
        self.view_widget = SnakeView(self.game, self.theme_manager, self.config)
        self.stats_widget = StatsPanel(self.game, self.theme_manager)
        
        # Create layout: game and stats side by side
        self.game_container = Horizontal(
            self.view_widget,
            self.stats_widget,
            id="game-content"
        )
        
        # Mount the game container
        self.mount(self.game_container)
        
        # Restart timer
        self.timer = self.set_interval(self.interval, self.tick)

    async def on_key(self, event: events.Key) -> None:
        # Handle pause screen
        if self.game and self.game.paused and self.pause_view:
            self.unpause_game()
            return
            
        if self.state_manager.is_state(GameState.SPLASH):
            # Any key starts from splash screen
            self.start_game()
            return
            
        if self.state_manager.is_state(GameState.GAME_OVER):
            # Q quits, any other key restarts
            if event.key.upper() == "Q":
                await self.action_quit()
            else:
                self.start_game()
            return
            
        key = event.key.upper()
        if key in ("UP", "DOWN", "LEFT", "RIGHT"):
            self.game.turn(Direction[key])
        elif key == "P":
            self.pause_game()
        elif key == "Q":
            await self.action_quit()

    async def on_ready(self) -> None:
        """Once the app is up, give focus to the splash screen so on_key fires."""
        if self.state_manager.is_state(GameState.SPLASH) and self.splash_view:
            self.splash_view.focus()

    async def on_resize(self, event: events.Resize) -> None:
        """Handle terminal resize by updating grid and scaling snake."""
        if self.game and self.view_widget:
            width, height = self.size
            game_width, game_height = self._calculate_game_dimensions(width, height)
            self.game.resize(game_width, game_height)
            self.view_widget.refresh()
            self.stats_widget.update_content()
