"""theme.py — single source of truth for the dark theme.

Every stylesheet in the app imports these tokens; change a value once. Hex
values match what shipped before this file existed (a no-op visual diff) —
preview.py's translucent chrome and the pin bar are intentionally a different
palette than the solid windows, so they get their own token group.
"""

# Solid window palette (launcher, history, settings, pin frame).
BG = "#161617"
PANEL = "#1f1f22"
PANEL_HOVER = "#2a2a2e"
BORDER = "#2e2e32"
BORDER_HOVER = "#3a3a40"
PIN_BORDER = "#52525b"

ACCENT = "#2563eb"
ACCENT_PRESSED = "#1d4ed8"

TEXT = "#e4e4e7"
TEXT_BODY = "#d4d4d8"
TEXT_MUTED = "#71717a"
TEXT_WHITE = "#ffffff"
WARNING = "#d49e5b"

# Translucent floating chrome (pin bar, preview window + its action buttons).
# These sit over arbitrary captured content, so they are deliberately darker
# and more neutral than the solid palette above.
CHROME_BAR_BG = "rgba(30, 30, 30, 190)"
CHROME_BG = "#1e1e1e"
CHROME_TEXT = "#cccccc"
CHROME_HOVER = "#333333"
CHROME_PRESSED = "#111111"
CHROME_BORDER = "#444444"
CHROME_BORDER_HOVER = "#666666"
CHROME_BTN_BG = "rgba(60, 60, 60, 200)"
CHROME_BTN_HOVER = "rgba(100, 100, 100, 230)"
CHROME_BTN_PRESSED = "rgba(40, 40, 40, 200)"
CHROME_BTN_BORDER = "rgba(120, 120, 120, 120)"
CHROME_BTN_BORDER_HOVER = "rgba(160, 160, 160, 200)"
CHROME_TILE_BG = "rgba(30, 30, 30, 180)"

# Radii.
RADIUS = "6px"
RADIUS_SMALL = "4px"
RADIUS_MID = "5px"
RADIUS_LARGE = "8px"
