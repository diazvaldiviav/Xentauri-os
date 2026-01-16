"""
ScreenshotExporter - Save diff images and screenshots to disk.

Sprint 5: Export functionality for debugging and analysis.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .diff_engine import DiffResult

logger = logging.getLogger(__name__)


@dataclass
class ExportedScreenshots:
    """Paths to exported screenshots."""

    before: str
    after: str
    diff_tight: Optional[str] = None
    diff_local: Optional[str] = None
    diff_global: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Serialize to dictionary."""
        return {
            "before": self.before,
            "after": self.after,
            "diff_tight": self.diff_tight,
            "diff_local": self.diff_local,
            "diff_global": self.diff_global,
        }

    @property
    def all_paths(self) -> list:
        """Get all non-None paths."""
        paths = [self.before, self.after]
        if self.diff_tight:
            paths.append(self.diff_tight)
        if self.diff_local:
            paths.append(self.diff_local)
        if self.diff_global:
            paths.append(self.diff_global)
        return paths


class ScreenshotExporter:
    """
    Exports screenshots and diff images to disk.

    Directory structure:
        {base_dir}/
            {session_id}/
                initial.png
                element_001_btn_submit/
                    before.png
                    after.png
                    diff_tight.png
                    diff_local.png
                    diff_global.png

    Usage:
        exporter = ScreenshotExporter("/tmp/validation_debug")
        paths = exporter.export(
            element_selector=".btn",
            before_screenshot=before_bytes,
            after_screenshot=after_bytes,
            diff_result=diff_result,
        )
        print(f"Screenshots saved to: {paths.before}")
    """

    DEFAULT_DIR = "/tmp/jarvis_sandbox_debug"

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the exporter.

        Args:
            base_dir: Base directory for all exports.
                      Defaults to /tmp/jarvis_sandbox_debug
        """
        self.base_dir = base_dir or self.DEFAULT_DIR
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._element_counter = 0

    def export(
        self,
        element_selector: str,
        before_screenshot: bytes,
        after_screenshot: bytes,
        diff_result: Optional[DiffResult] = None,
    ) -> ExportedScreenshots:
        """
        Export screenshots for an element.

        Args:
            element_selector: CSS selector (used for folder naming)
            before_screenshot: PNG bytes before click
            after_screenshot: PNG bytes after click
            diff_result: Optional DiffResult with diff images

        Returns:
            ExportedScreenshots with file paths
        """
        self._element_counter += 1

        # Create safe folder name from selector
        safe_name = self._sanitize_selector(element_selector)
        folder_name = f"element_{self._element_counter:03d}_{safe_name}"

        element_dir = os.path.join(
            self.base_dir,
            self.session_id,
            folder_name
        )
        os.makedirs(element_dir, exist_ok=True)

        # Save before/after
        before_path = os.path.join(element_dir, "before.png")
        after_path = os.path.join(element_dir, "after.png")

        self._save_png(before_screenshot, before_path)
        self._save_png(after_screenshot, after_path)

        result = ExportedScreenshots(before=before_path, after=after_path)

        # Save diff images if available
        if diff_result:
            if diff_result.tight.diff_image:
                result.diff_tight = os.path.join(element_dir, "diff_tight.png")
                self._save_png(diff_result.tight.diff_image, result.diff_tight)

            if diff_result.local.diff_image:
                result.diff_local = os.path.join(element_dir, "diff_local.png")
                self._save_png(diff_result.local.diff_image, result.diff_local)

            if diff_result.global_.diff_image:
                result.diff_global = os.path.join(element_dir, "diff_global.png")
                self._save_png(diff_result.global_.diff_image, result.diff_global)

        logger.debug(f"Exported screenshots to {element_dir}")
        return result

    def export_initial(self, screenshot: bytes, name: str = "initial") -> str:
        """
        Export initial page screenshot.

        Args:
            screenshot: PNG bytes of initial page state
            name: Filename without extension

        Returns:
            Path to saved file
        """
        session_dir = os.path.join(self.base_dir, self.session_id)
        os.makedirs(session_dir, exist_ok=True)

        path = os.path.join(session_dir, f"{name}.png")
        self._save_png(screenshot, path)
        return path

    def get_session_dir(self) -> str:
        """
        Get the current session directory path.

        Returns:
            Absolute path to session directory
        """
        return os.path.join(self.base_dir, self.session_id)

    def reset_counter(self) -> None:
        """Reset the element counter. Useful for testing."""
        self._element_counter = 0

    def new_session(self) -> str:
        """
        Start a new session with a new timestamp.

        Returns:
            New session ID
        """
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._element_counter = 0
        return self.session_id

    def _save_png(self, data: bytes, path: str) -> bool:
        """
        Save PNG bytes to file.

        Args:
            data: PNG image bytes
            path: Target file path

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            logger.warning(f"Failed to save screenshot to {path}: {e}")
            return False

    def _sanitize_selector(self, selector: str) -> str:
        """
        Convert selector to safe filename component.

        Args:
            selector: CSS selector

        Returns:
            Safe string for use in filenames
        """
        # Replace common selector characters
        safe = selector
        for char in ".#[]='\"(){}:> ,+~":
            safe = safe.replace(char, "_")
        # Remove multiple underscores
        while "__" in safe:
            safe = safe.replace("__", "_")
        # Limit length and trim
        return safe[:40].strip("_")

    def cleanup_session(self) -> bool:
        """
        Delete all files from the current session.

        Returns:
            True if cleanup was successful
        """
        import shutil
        session_dir = self.get_session_dir()
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
            return True
        except Exception as e:
            logger.warning(f"Failed to cleanup session {session_dir}: {e}")
            return False
