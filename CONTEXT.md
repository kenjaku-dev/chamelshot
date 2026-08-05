# ChamelShot — Glossary

- **Pin** — an in-memory copy of the current screenshot shown as a frameless,
  always-on-top, draggable window. Multiple pins can coexist; they are
  ephemeral (not saved to history) and all close when the app quits.
- **PinStore** — the Qt-free state model tracking open pins: add, remove,
  close_all, count. GUI never touches this directly except via PinWindow.
- **PinWindow** — the frameless Qt widget that renders a pin: pixel-size image
  inside a scroll area (window capped to the screen), drag-to-move, Escape to
  close, hover action bar (Copy / Save / Re-edit / Close).
- **Re-edit (pin)** — loads the pinned image back into a PreviewWindow for
  annotation/saving, via the same `_reopen_for_edit` seam used by history.
