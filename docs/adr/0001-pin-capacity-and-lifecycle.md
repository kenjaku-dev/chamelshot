# 0001 — Pins: multiple, additive, ephemeral

Status: accepted

Context: the v5 "pin screenshot on screen" feature (C1) needed a capacity
decision. Wlroots screen-share pins (Flameshot) allow several to be pinned at
once; single-capacity apps replace the previous pin.

Decision: pins are multiple and additive. A pin never replaces another; each
`PinWindow` is self-contained and tracked in a list on the app. They are
ephemeral — a pin is not copied into history and produces no file on disk;
closing the app closes all pins. The state model (`PinStore`) holds opaque
handles and is GUI-free so unit tests need no Qt.

Consequences: no "replace last pin" edge logic; the user can pin several
references side by side. Pinned references vanish on quit (pins are meant to
outlive neither the daemon nor the workspace session).