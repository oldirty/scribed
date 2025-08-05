"""Clipboard utilities for Scribed."""

import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class ClipboardManager:
    """Cross-platform clipboard manager."""

    def __init__(self):
        """Initialize clipboard manager with platform-specific backend."""
        self._backend = None
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize the appropriate clipboard backend for the current platform."""
        try:
            if sys.platform.startswith("win"):
                self._backend = self._init_windows_backend()
            elif sys.platform.startswith("darwin"):
                self._backend = self._init_macos_backend()
            else:
                self._backend = self._init_linux_backend()

            logger.info(
                f"Initialized clipboard backend: {type(self._backend).__name__}"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize clipboard backend: {e}")
            self._backend = None

    def _init_windows_backend(self):
        """Initialize Windows clipboard backend."""
        try:
            import win32clipboard

            return WindowsClipboard()
        except ImportError:
            try:
                import tkinter as tk

                return TkinterClipboard()
            except ImportError:
                raise ImportError("No Windows clipboard backend available")

    def _init_macos_backend(self):
        """Initialize macOS clipboard backend."""
        try:
            import subprocess

            return MacOSClipboard()
        except Exception:
            try:
                import tkinter as tk

                return TkinterClipboard()
            except ImportError:
                raise ImportError("No macOS clipboard backend available")

    def _init_linux_backend(self):
        """Initialize Linux clipboard backend."""
        try:
            import subprocess

            return LinuxClipboard()
        except Exception:
            try:
                import tkinter as tk

                return TkinterClipboard()
            except ImportError:
                raise ImportError("No Linux clipboard backend available")

    def set_text(self, text: str) -> bool:
        """Set text in clipboard.

        Args:
            text: Text to set in clipboard

        Returns:
            True if successful, False otherwise
        """
        if not self._backend:
            logger.error("No clipboard backend available")
            return False

        try:
            return self._backend.set_text(text)
        except Exception as e:
            logger.error(f"Failed to set clipboard text: {e}")
            return False

    def get_text(self) -> Optional[str]:
        """Get text from clipboard.

        Returns:
            Clipboard text or None if unavailable
        """
        if not self._backend:
            logger.error("No clipboard backend available")
            return None

        try:
            return self._backend.get_text()
        except Exception as e:
            logger.error(f"Failed to get clipboard text: {e}")
            return None

    def is_available(self) -> bool:
        """Check if clipboard is available."""
        return self._backend is not None


class WindowsClipboard:
    """Windows-specific clipboard implementation using win32clipboard."""

    def set_text(self, text: str) -> bool:
        """Set text in Windows clipboard."""
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text)
            return True
        finally:
            win32clipboard.CloseClipboard()

    def get_text(self) -> Optional[str]:
        """Get text from Windows clipboard."""
        import win32clipboard

        try:
            win32clipboard.OpenClipboard()
            try:
                return win32clipboard.GetClipboardData()
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return None


class MacOSClipboard:
    """macOS-specific clipboard implementation using pbcopy/pbpaste."""

    def set_text(self, text: str) -> bool:
        """Set text in macOS clipboard."""
        import subprocess

        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return process.returncode == 0
        except Exception:
            return False

    def get_text(self) -> Optional[str]:
        """Get text from macOS clipboard."""
        import subprocess

        try:
            result = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, check=True
            )
            return result.stdout
        except Exception:
            return None


class LinuxClipboard:
    """Linux-specific clipboard implementation using xclip/xsel."""

    def set_text(self, text: str) -> bool:
        """Set text in Linux clipboard."""
        import subprocess

        # Try xclip first
        try:
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True
            )
            process.communicate(input=text)
            if process.returncode == 0:
                return True
        except FileNotFoundError:
            pass

        # Try xsel as fallback
        try:
            process = subprocess.Popen(
                ["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE, text=True
            )
            process.communicate(input=text)
            return process.returncode == 0
        except FileNotFoundError:
            return False

    def get_text(self) -> Optional[str]:
        """Get text from Linux clipboard."""
        import subprocess

        # Try xclip first
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Try xsel as fallback
        try:
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None


class TkinterClipboard:
    """Cross-platform clipboard implementation using tkinter."""

    def __init__(self):
        """Initialize tkinter clipboard."""
        import tkinter as tk

        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window

    def set_text(self, text: str) -> bool:
        """Set text in clipboard using tkinter."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()  # Required to make the clipboard persist
            return True
        except Exception:
            return False

    def get_text(self) -> Optional[str]:
        """Get text from clipboard using tkinter."""
        try:
            return self.root.clipboard_get()
        except Exception:
            return None


# Global clipboard manager instance
_clipboard_manager: Optional[ClipboardManager] = None


def get_clipboard_manager() -> ClipboardManager:
    """Get the global clipboard manager instance."""
    global _clipboard_manager
    if _clipboard_manager is None:
        _clipboard_manager = ClipboardManager()
    return _clipboard_manager


def set_clipboard_text(text: str) -> bool:
    """Convenience function to set clipboard text.

    Args:
        text: Text to set in clipboard

    Returns:
        True if successful, False otherwise
    """
    return get_clipboard_manager().set_text(text)


def get_clipboard_text() -> Optional[str]:
    """Convenience function to get clipboard text.

    Returns:
        Clipboard text or None if unavailable
    """
    return get_clipboard_manager().get_text()


def is_clipboard_available() -> bool:
    """Check if clipboard functionality is available."""
    return get_clipboard_manager().is_available()
