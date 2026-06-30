import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)

class UndoManager:
    """Manages undo/redo state stack for the application.

    Stores deep copies of application state snapshots.
    Max stack size prevents memory bloat.
    """

    def __init__(self, max_states: int = 20):
        """Initialize with max number of states to keep."""
        self.max_states = max_states
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    def push_state(self, state: dict, label: str = ""):
        """Push a new state onto the undo stack.

        Clears the redo stack (new action invalidates redo history).
        Deep copies the state to prevent reference issues.

        Args:
            state: dict with application state to save
            label: human-readable description of the action (for logging)
        """
        snapshot = copy.deepcopy(state)
        snapshot['_undo_label'] = label
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()

        # Trim oldest if over limit
        if len(self._undo_stack) > self.max_states:
            self._undo_stack.pop(0)

        logger.info("Stato salvato: '%s' (stack: %d)", label, len(self._undo_stack))

    def undo(self) -> dict | None:
        """Undo last action. Returns previous state or None if nothing to undo.

        Moves current state to redo stack before returning previous.
        """
        if not self._undo_stack:
            logger.info("Niente da annullare")
            return None

        current = self._undo_stack.pop()
        self._redo_stack.append(current)

        if self._undo_stack:
            result = copy.deepcopy(self._undo_stack[-1])
            label = result.pop('_undo_label', '')
            logger.info("Undo: tornato a '%s' (undo: %d, redo: %d)",
                       label, len(self._undo_stack), len(self._redo_stack))
            return result
        else:
            # Return empty state (initial state)
            logger.info("Undo: tornato allo stato iniziale")
            return {}

    def redo(self) -> dict | None:
        """Redo last undone action. Returns next state or None if nothing to redo."""
        if not self._redo_stack:
            logger.info("Niente da ripristinare")
            return None

        state = self._redo_stack.pop()
        self._undo_stack.append(state)

        result = copy.deepcopy(state)
        label = result.pop('_undo_label', '')
        logger.info("Redo: ripristinato '%s' (undo: %d, redo: %d)",
                    label, len(self._undo_stack), len(self._redo_stack))
        return result

    @property
    def can_undo(self) -> bool:
        """True if there's at least one state to undo to."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """True if there's at least one state to redo."""
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.info("Cronologia undo/redo cancellata")

    def peek_undo_label(self) -> str:
        """Get the label of the next undo action without performing it."""
        if self._undo_stack:
            return self._undo_stack[-1].get('_undo_label', '')
        return ''

    def peek_redo_label(self) -> str:
        """Get the label of the next redo action without performing it."""
        if self._redo_stack:
            return self._redo_stack[-1].get('_undo_label', '')
        return ''
