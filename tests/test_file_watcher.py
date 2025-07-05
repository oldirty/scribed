"""Test file watcher functionality."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from scribed.audio.file_watcher import FileWatcher, AudioFileHandler
from scribed.config import Config
from scribed.daemon import ScribedDaemon


class TestAudioFileHandler:
    """Test AudioFileHandler class."""
    
    @pytest.fixture
    def file_watcher(self):
        """Create mock file watcher."""
        watcher = Mock(spec=FileWatcher)
        watcher.supported_formats = {".wav", ".mp3", ".flac"}
        watcher.process_file = AsyncMock()
        return watcher
    
    @pytest.fixture
    def handler(self, file_watcher):
        """Create handler instance."""
        return AudioFileHandler(file_watcher)
    
    def test_init(self, handler, file_watcher):
        """Test handler initialization."""
        assert handler.file_watcher == file_watcher
    
    def test_on_created_directory(self, handler):
        """Test handling directory creation (should be ignored)."""
        event = Mock()
        event.is_directory = True
        event.src_path = "/test/directory"
        
        # Should not call process_file for directories
        handler.on_created(event)
        handler.file_watcher.process_file.assert_not_called()
    
    def test_on_created_unsupported_file(self, handler):
        """Test handling unsupported file creation."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/test/file.txt"  # Unsupported format
        
        handler.on_created(event)
        handler.file_watcher.process_file.assert_not_called()
    
    def test_on_created_supported_file(self, handler):
        """Test handling supported file creation."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/test/audio.wav"
        
        with patch("asyncio.create_task") as mock_create_task:
            handler.on_created(event)
            mock_create_task.assert_called_once()


class TestFileWatcher:
    """Test FileWatcher class."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            watch_dir = temp_path / "watch"
            output_dir = temp_path / "output"
            watch_dir.mkdir()
            output_dir.mkdir()
            yield {
                "watch": str(watch_dir),
                "output": str(output_dir),
                "temp": str(temp_path)
            }
    
    @pytest.fixture
    def config(self, temp_dirs):
        """Create test configuration."""
        return Config(
            file_watcher={
                "watch_directory": temp_dirs["watch"],
                "output_directory": temp_dirs["output"],
                "supported_formats": [".wav", ".mp3", ".flac"]
            }
        )
    
    @pytest.fixture
    def daemon(self):
        """Create mock daemon."""
        return Mock(spec=ScribedDaemon)
    
    @pytest.fixture
    def file_watcher(self, config, daemon):
        """Create file watcher instance."""
        return FileWatcher(config, daemon)
    
    def test_init(self, file_watcher, config):
        """Test file watcher initialization."""
        assert file_watcher.config == config
        assert file_watcher.supported_formats == {".wav", ".mp3", ".flac"}
        assert Path(file_watcher.watch_directory).exists()
        assert Path(file_watcher.output_directory).exists()
        assert not file_watcher._running
        assert len(file_watcher._processed_files) == 0
    
    @pytest.mark.asyncio
    async def test_start(self, file_watcher):
        """Test starting file watcher."""
        with patch.object(file_watcher.observer, "start") as mock_start, \
             patch.object(file_watcher, "_process_existing_files") as mock_process:
            
            await file_watcher.start()
            
            mock_start.assert_called_once()
            mock_process.assert_called_once()
            assert file_watcher._running is True
    
    @pytest.mark.asyncio
    async def test_start_already_running(self, file_watcher):
        """Test starting when already running."""
        file_watcher._running = True
        
        with patch.object(file_watcher.observer, "start") as mock_start:
            await file_watcher.start()
            mock_start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stop(self, file_watcher):
        """Test stopping file watcher."""
        file_watcher._running = True
        
        with patch.object(file_watcher.observer, "stop") as mock_stop, \
             patch.object(file_watcher.observer, "join") as mock_join:
            
            await file_watcher.stop()
            
            mock_stop.assert_called_once()
            mock_join.assert_called_once()
            assert file_watcher._running is False
    
    @pytest.mark.asyncio
    async def test_stop_not_running(self, file_watcher):
        """Test stopping when not running."""
        with patch.object(file_watcher.observer, "stop") as mock_stop:
            await file_watcher.stop()
            mock_stop.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_existing_files(self, file_watcher, temp_dirs):
        """Test processing existing files."""
        # Create test audio files
        watch_dir = Path(temp_dirs["watch"])
        (watch_dir / "test1.wav").write_text("dummy audio data")
        (watch_dir / "test2.mp3").write_text("dummy audio data")
        (watch_dir / "ignore.txt").write_text("not audio")
        
        with patch.object(file_watcher, "process_file") as mock_process:
            await file_watcher._process_existing_files()
            
            # Should process only audio files
            assert mock_process.call_count == 2
            processed_files = [call[0][0].name for call in mock_process.call_args_list]
            assert "test1.wav" in processed_files
            assert "test2.mp3" in processed_files
    
    @pytest.mark.asyncio
    async def test_process_file(self, file_watcher, temp_dirs):
        """Test processing a single file."""
        # Create test file
        watch_dir = Path(temp_dirs["watch"])
        output_dir = Path(temp_dirs["output"])
        test_file = watch_dir / "test.wav"
        test_file.write_text("dummy audio data")
        
        await file_watcher.process_file(test_file)
        
        # Check if transcription file was created
        output_file = output_dir / "test.txt"
        assert output_file.exists()
        
        # Check file was marked as processed
        assert test_file in file_watcher._processed_files
        
        # Check transcription content
        content = output_file.read_text()
        assert "Transcription placeholder" in content
        assert test_file.name in content
    
    @pytest.mark.asyncio
    async def test_process_file_already_processed(self, file_watcher, temp_dirs):
        """Test processing file that was already processed."""
        watch_dir = Path(temp_dirs["watch"])
        test_file = watch_dir / "test.wav"
        test_file.write_text("dummy audio data")
        
        # Mark as already processed
        file_watcher._processed_files.add(test_file)
        
        await file_watcher.process_file(test_file)
        
        # Should not create output file
        output_file = Path(temp_dirs["output"]) / "test.txt"
        assert not output_file.exists()
    
    @pytest.mark.asyncio
    async def test_process_file_error_handling(self, file_watcher, temp_dirs):
        """Test error handling during file processing."""
        watch_dir = Path(temp_dirs["watch"])
        test_file = watch_dir / "test.wav"
        test_file.write_text("dummy audio data")
        
        # Mock file operation to raise exception
        with patch("builtins.open", side_effect=IOError("Test error")):
            await file_watcher.process_file(test_file)
            
            # File should be removed from processed set on error
            assert test_file not in file_watcher._processed_files
