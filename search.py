#!/usr/bin/env python3
"""searchable_directory_tree.py – FAST REFACTORED VERSION

A **drop‑in** searchable / filterable DirectoryTree that works only with
visible/expanded items for maximum performance.

Key improvements in this refactor:
----------------------------------
1. **No recursive directory scanning** – only filters immediate children of expanded nodes
2. **Instant search** – searches only through currently visible/expanded items
3. **Smart filtering** – shows matching files in expanded folders, hides non-matching folders
4. **Image filtering** – toggle between all files and images only
5. **Responsive UI** – no delays or throttling needed due to minimal processing

Run the file directly to launch the demo:

    python searchable_directory_tree.py

Controls
~~~~~~~~
• **Type** – live search through visible items
• **F2**  – images‑only toggle (png / jpg / gif …)
• **F3**  – show / hide dot‑files
• **Ctrl‑C** – quit demo
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import DirectoryTree, Footer, Header, Input, Static

__all__ = ["SearchableDirectoryTree"]

# ────────────────────────────── helpers ────────────────────────────── #
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg", ".ico", ".avif"}

def is_image(path: Path) -> bool:
    """Return True if path has an image extension."""
    return path.suffix.lower() in IMG_EXTS

def matches_search(name: str, search_term: str) -> bool:
    """Check if filename matches search term (case-insensitive)."""
    if not search_term:
        return True
    return search_term.lower() in name.lower()

# ─────────────────────────── main widget ──────────────────────────── #
class SearchableDirectoryTree(DirectoryTree):
    """DirectoryTree with fast search through visible/expanded items only."""

    search_term: reactive[str] = reactive("")
    images_only: reactive[bool] = reactive(False)
    show_hidden: reactive[bool] = reactive(False)

    def __init__(
        self,
        path: str | os.PathLike,
        *,
        search: str = "",
        images_only: bool = False,
        show_hidden: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(path, **kwargs)
        self.search_term = search
        self.images_only = images_only
        self.show_hidden = show_hidden
        self._search_timer: Timer | None = None
        self._pending_filters: dict = {}

    # Public ------------------------------------------------------------------ #
    def set_filters(
        self,
        *,
        search: str | None = None,
        images_only: bool | None = None,
        show_hidden: bool | None = None,
    ) -> None:
        """Change any filter with 1-second debouncing to prevent rapid reloads."""
        # Store the pending filter changes
        if search is not None:
            self._pending_filters['search'] = search
        if images_only is not None:
            self._pending_filters['images_only'] = images_only
        if show_hidden is not None:
            self._pending_filters['show_hidden'] = show_hidden
        
        # Cancel any existing timer
        if self._search_timer is not None:
            self._search_timer.stop()
        
        # For non-search filters (images_only, show_hidden), apply immediately
        # Only debounce search input since that's what users type rapidly
        if search is None and (images_only is not None or show_hidden is not None):
            self._apply_pending_filters()
        else:
            # Start a new timer for search input (1 second delay)
            self._search_timer = self.set_timer(1.0, self._apply_pending_filters)

    def _apply_pending_filters(self) -> None:
        """Apply all pending filter changes."""
        # Apply the stored filter values
        if 'search' in self._pending_filters:
            self.search_term = self._pending_filters['search']
        if 'images_only' in self._pending_filters:
            self.images_only = self._pending_filters['images_only']
        if 'show_hidden' in self._pending_filters:
            self.show_hidden = self._pending_filters['show_hidden']
        
        # Clear pending filters
        self._pending_filters.clear()
        self._search_timer = None
        
        # Now apply the filters
        self._force_full_reload()

    def _force_full_reload(self) -> None:
        """Force a complete reload of the tree including all expanded nodes."""
        # Store the current expanded state
        expanded_paths = self._get_expanded_paths()
        
        # Reload the entire tree
        self.reload()
        
        # Restore the expanded state after a short delay
        self.call_later(lambda: self._restore_expanded_state(expanded_paths))
    
    def _get_expanded_paths(self) -> set[str]:
        """Get the paths of all currently expanded directories."""
        expanded = set()
        
        def collect_expanded(node):
            if hasattr(node, 'is_expanded') and node.is_expanded and hasattr(node, 'data') and node.data:
                try:
                    expanded.add(str(node.data.path))
                except Exception:
                    pass
            if hasattr(node, 'children'):
                for child in node.children:
                    collect_expanded(child)
        
        if hasattr(self, 'root') and self.root:
            collect_expanded(self.root)
        
        return expanded
    
    def _restore_expanded_state(self, expanded_paths: set[str]) -> None:
        """Restore the expanded state of directories."""
        def expand_matching(node):
            if hasattr(node, 'data') and node.data:
                try:
                    if str(node.data.path) in expanded_paths:
                        node.expand()
                except Exception:
                    pass
            if hasattr(node, 'children'):
                for child in node.children:
                    expand_matching(child)
        
        if hasattr(self, 'root') and self.root:
            expand_matching(self.root)

    # Internal ---------------------------------------------------------------- #
    def filter_paths(self, paths: Iterable[Path]) -> List[Path]:
        """Filter only the immediate children paths (visible items only)."""
        search = self.search_term.strip()
        img_only = self.images_only
        show_hidden = self.show_hidden
        filtered: list[Path] = []

        for path in paths:
            name = path.name

            # Skip hidden files/folders unless show_hidden is enabled
            if not show_hidden and name.startswith("."):
                continue

            is_file = path.is_file()
            is_dir = path.is_dir()

            # Handle files
            if is_file:
                # Check if filename matches search term
                if search and not matches_search(name, search):
                    continue
                
                # Check image filter
                if img_only and not is_image(path):
                    continue
                
                # File passed all filters
                filtered.append(path)
            
            # Handle directories
            elif is_dir:
                # For directories, we always include them if they pass basic filters
                # The user can expand them to see their contents
                # We only filter by search term if it's a direct match
                if search:
                    # If directory name doesn't match search term, we still include it
                    # because it might contain matching files when expanded
                    # But if it does match, we definitely include it
                    pass
                
                # Directory passed filters
                filtered.append(path)

        return filtered


# ───────────────────────────── demo app ───────────────────────────── #
class _Demo(App):
    """Demo app showcasing the fast searchable directory tree."""

    CSS = """
    Screen {
        background: $surface;
    }
    
    #toolbar {
        height: 3;
        width: 100%;
        background: $panel;
        padding: 0 1;
    }
    
    #search_icon {
        width: 3;
        text-align: center;
        content-align: center middle;
    }
    
    #search_box {
        width: 1fr;
        margin: 0 1;
    }
    
    #hints {
        width: auto;
        content-align: center middle;
        color: $text-muted;
    }
    
    #status {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("f2", "toggle_images", "Images only"),
        ("f3", "toggle_hidden", "Show hidden"),
        ("ctrl+c", "quit", "Quit"),
    ]

    @property
    def dir_tree(self) -> SearchableDirectoryTree:
        """Get the directory tree widget."""
        return self.query_one(SearchableDirectoryTree)

    @property
    def status(self) -> Static:
        """Get the status widget."""
        return self.query_one("#status", Static)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="toolbar"):
            yield Static("🔍", id="search_icon")
            yield Input(placeholder="Search files in expanded folders…", id="search_box")
            yield Static("F2 images‑only  •  F3 hidden  •  Ctrl‑C quit", id="hints")
        yield SearchableDirectoryTree("./", id="tree")
        yield Static("Ready - expand folders and search through visible items", id="status")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the search box when app starts."""
        self.query_one("#search_box", Input).focus()

    def update_status(self) -> None:
        """Update the status line with current filter info."""
        tree = self.dir_tree
        status_parts = []
        
        # Check if there's a pending search
        if tree._search_timer is not None and 'search' in tree._pending_filters:
            pending_search = tree._pending_filters['search']
            if pending_search:
                status_parts.append(f"Searching for: '{pending_search}' (pending...)")
            else:
                status_parts.append("Clearing search (pending...)")
        elif tree.search_term:
            status_parts.append(f"Search: '{tree.search_term}'")
        
        if tree.images_only:
            status_parts.append("Images only")
        
        if tree.show_hidden:
            status_parts.append("Showing hidden")
        
        if status_parts:
            self.status.update(" • ".join(status_parts))
        else:
            self.status.update("Ready - expand folders and search through visible items")

    # ───────────────────────── callbacks / actions ─────────────────────────── #
    def on_input_changed(self, msg: Input.Changed) -> None:
        """Handle search input changes."""
        if msg.input.id == "search_box":
            self.dir_tree.set_filters(search=msg.value)
            self.update_status()
            # Update status again after a short delay to show when search completes
            self.set_timer(1.1, self.update_status)

    def action_toggle_images(self) -> None:
        """Toggle images-only filter."""
        current = self.dir_tree.images_only
        self.dir_tree.set_filters(images_only=not current)
        self.update_status()

    def action_toggle_hidden(self) -> None:
        """Toggle show hidden files filter."""
        current = self.dir_tree.show_hidden
        self.dir_tree.set_filters(show_hidden=not current)
        self.update_status()


if __name__ == "__main__":
    _Demo().run()
