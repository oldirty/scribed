"""Tests for output handling system."""

import asyncio
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scribed.output import (
    OutputHandler,
    OutputConfig,
    FileOutput,
    ClipboardOutput,
    ConsoleOutput,
    OutputStatus,
)


class TestFileOutput:
    """Tests for FileOutput class."""

    def test_file_output_init(self):
        """Test FileOutput initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {"output_directory": temp_dir}
            file_output = FileOutput(config)
            assert file_output.is_available()
            assert file_output.name == "file"

    @pytest.mark.asyncio
    async def test_file_output_write_txt(self):
        """Test writing text format to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "output_directory": temp_dir,
                "format": "txt",
                "filename_template": "test_{timestamp}",
            }
            file_output = FileOutput(config)

            result = await file_output.write("Test transcription", {"source": "test"})

            assert result.status == OutputStatus.SUCCESS
            assert "test_" in result.message

            # Check file was created
            files = list(Path(temp_dir).glob("test_*.txt"))
            assert len(files) == 1

            # Check content
            content = files[0].read_text(encoding="utf-8")
            assert "Test transcription" in content

    @pytest.mark.asyncio
    async def test_file_output_write_json(self):
        """Test writing JSON format to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "output_directory": temp_dir,
                "format": "json",
                "filename_template": "test_{timestamp}",
            }
            file_output = FileOutput(config)

            result = await file_output.write("Test transcription", {"source": "test"})

            assert result.status == OutputStatus.SUCCESS

            # Check file was created
            files = list(Path(temp_dir).glob("test_*.json"))
            assert len(files) == 1

            # Check content is valid JSON
            import json

            content = json.loads(files[0].read_text(encoding="utf-8"))
            assert content["text"] == "Test transcription"
            assert "metadata" in content


class TestClipboardOutput:
    """Tests for ClipboardOutput class."""

    @patch("scribed.clipboard.get_clipboard_manager")
    def test_clipboard_output_init(self, mock_get_manager):
        """Test ClipboardOutput initialization."""
        mock_manager = Mock()
        mock_manager.is_available.return_value = True
        mock_get_manager.return_value = mock_manager

        config = {}
        clipboard_output = ClipboardOutput(config)
        assert clipboard_output.name == "clipboard"

    @pytest.mark.asyncio
    @patch("scribed.clipboard.get_clipboard_manager")
    async def test_clipboard_output_write(self, mock_get_manager):
        """Test writing to clipboard."""
        mock_manager = Mock()
        mock_manager.is_available.return_value = True
        mock_manager.set_text.return_value = True
        mock_get_manager.return_value = mock_manager

        config = {"format": "plain"}
        clipboard_output = ClipboardOutput(config)

        result = await clipboard_output.write("Test transcription")

        assert result.status == OutputStatus.SUCCESS
        mock_manager.set_text.assert_called_once_with("Test transcription")


class TestConsoleOutput:
    """Tests for ConsoleOutput class."""

    def test_console_output_init(self):
        """Test ConsoleOutput initialization."""
        config = {}
        console_output = ConsoleOutput(config)
        assert console_output.is_available()
        assert console_output.name == "console"

    @pytest.mark.asyncio
    @patch("builtins.print")
    async def test_console_output_write(self, mock_print):
        """Test writing to console."""
        config = {"format": "plain"}
        console_output = ConsoleOutput(config)

        result = await console_output.write("Test transcription")

        assert result.status == OutputStatus.SUCCESS
        mock_print.assert_called_once()


class TestOutputHandler:
    """Tests for OutputHandler class."""

    def test_output_handler_init_file_only(self):
        """Test OutputHandler with file output only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = OutputConfig(
                save_to_file=True,
                copy_to_clipboard=False,
                console_output=False,
                file_config={"output_directory": temp_dir},
            )
            handler = OutputHandler(config)

            assert len(handler.destinations) == 1
            assert handler.destinations[0].name == "file"
            assert handler.is_any_destination_available()

    @patch("scribed.clipboard.get_clipboard_manager")
    def test_output_handler_init_multiple(self, mock_get_manager):
        """Test OutputHandler with multiple destinations."""
        mock_manager = Mock()
        mock_manager.is_available.return_value = True
        mock_get_manager.return_value = mock_manager

        with tempfile.TemporaryDirectory() as temp_dir:
            config = OutputConfig(
                save_to_file=True,
                copy_to_clipboard=True,
                console_output=True,
                file_config={"output_directory": temp_dir},
            )
            handler = OutputHandler(config)

            assert len(handler.destinations) == 3
            destination_names = [dest.name for dest in handler.destinations]
            assert "file" in destination_names
            assert "clipboard" in destination_names
            assert "console" in destination_names

    @pytest.mark.asyncio
    @patch("scribed.clipboard.get_clipboard_manager")
    @patch("builtins.print")
    async def test_output_handler_write_transcription(
        self, mock_print, mock_get_manager
    ):
        """Test writing transcription to multiple destinations."""
        mock_manager = Mock()
        mock_manager.is_available.return_value = True
        mock_manager.set_text.return_value = True
        mock_get_manager.return_value = mock_manager

        with tempfile.TemporaryDirectory() as temp_dir:
            config = OutputConfig(
                save_to_file=True,
                copy_to_clipboard=True,
                console_output=True,
                file_config={"output_directory": temp_dir},
            )
            handler = OutputHandler(config)

            results = await handler.write_transcription("Test transcription")

            assert len(results) == 3
            assert all(result.status == OutputStatus.SUCCESS for result in results)

            # Check file was created
            files = list(Path(temp_dir).glob("*.txt"))
            assert len(files) == 1

            # Check clipboard was called
            mock_manager.set_text.assert_called_once()

            # Check console was called
            mock_print.assert_called_once()

    def test_get_available_destinations(self):
        """Test getting available destinations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = OutputConfig(
                save_to_file=True,
                copy_to_clipboard=False,
                console_output=True,
                file_config={"output_directory": temp_dir},
            )
            handler = OutputHandler(config)

            destinations = handler.get_available_destinations()
            assert "file" in destinations
            assert "console" in destinations
            assert len(destinations) == 2
