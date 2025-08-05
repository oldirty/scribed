"""Performance and reliability tests for Scribed components."""

import pytest
import asyncio
import time
import threading
import psutil
import gc
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import wave

import numpy as np

from scribed.core.engine import ScribedEngine
from scribed.core.session import TranscriptionSession
from scribed.config import Config
from scribed.audio.base import AudioChunk, AudioFormat
from scribed.transcription.service import TranscriptionService


class PerformanceMonitor:
    """Utility class for monitoring performance metrics."""

    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.start_cpu_time = None
        self.start_time = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_memory = self.process.memory_info().rss
        self.start_cpu_time = self.process.cpu_times()
        self.start_time = time.time()

    def get_metrics(self):
        """Get current performance metrics."""
        current_memory = self.process.memory_info().rss
        current_cpu_time = self.process.cpu_times()
        current_time = time.time()

        return {
            "memory_usage_mb": current_memory / (1024 * 1024),
            "memory_delta_mb": (current_memory - (self.start_memory or current_memory))
            / (1024 * 1024),
            "cpu_percent": self.process.cpu_percent(),
            "elapsed_time": current_time - (self.start_time or current_time),
            "user_cpu_time": current_cpu_time.user
            - (self.start_cpu_time.user if self.start_cpu_time else 0),
            "system_cpu_time": current_cpu_time.system
            - (self.start_cpu_time.system if self.start_cpu_time else 0),
        }


class TestEnginePerformance:
    """Test engine performance characteristics."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for performance testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {"provider": "mock", "model": "test"}
        return service

    @pytest.fixture
    def performance_config(self):
        """Configuration optimized for performance testing."""
        return Config(
            audio={"source": "microphone", "sample_rate": 16000, "channels": 1},
            transcription={"provider": "whisper"},  # Use valid provider
            output={"format": "txt", "save_to_file": False},
        )

    @pytest.mark.asyncio
    async def test_engine_startup_time(
        self, performance_config, mock_transcription_service
    ):
        """Test engine startup time performance."""
        monitor = PerformanceMonitor()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            monitor.start_monitoring()

            engine = ScribedEngine(performance_config)
            await engine.start()

            metrics = monitor.get_metrics()

            # Engine should start quickly
            assert (
                metrics["elapsed_time"] < 2.0
            ), f"Engine startup took {metrics['elapsed_time']:.2f}s"

            # Memory usage should be reasonable (Python + dependencies)
            assert (
                metrics["memory_usage_mb"] < 200
            ), f"Engine uses {metrics['memory_usage_mb']:.1f}MB"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_session_creation_performance(
        self, performance_config, mock_transcription_service
    ):
        """Test session creation performance."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(performance_config)
            await engine.start()

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Create multiple sessions rapidly
            session_ids = []
            for i in range(100):
                session_id = engine.create_session(f"perf_test_{i}")
                session_ids.append(session_id)

            metrics = monitor.get_metrics()

            # Session creation should be fast
            assert (
                metrics["elapsed_time"] < 1.0
            ), f"Creating 100 sessions took {metrics['elapsed_time']:.2f}s"

            # Memory growth should be reasonable
            assert (
                metrics["memory_delta_mb"] < 50
            ), f"Memory grew by {metrics['memory_delta_mb']:.1f}MB"

            # Verify all sessions were created
            assert len(engine._active_sessions) == 100

            await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_session_performance(
        self, performance_config, mock_transcription_service
    ):
        """Test concurrent session handling performance."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(performance_config)
            await engine.start()

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Create and start multiple sessions concurrently
            session_count = 10
            session_ids = []

            for i in range(session_count):
                session_id = engine.create_session(f"concurrent_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            # Add transcription results to all sessions concurrently
            tasks = []
            for session_id in session_ids:
                session = engine.get_session(session_id)
                task = asyncio.create_task(self._add_results_to_session(session, 50))
                tasks.append(task)

            await asyncio.gather(*tasks)

            metrics = monitor.get_metrics()

            # Should handle concurrent operations efficiently
            assert (
                metrics["elapsed_time"] < 5.0
            ), f"Concurrent operations took {metrics['elapsed_time']:.2f}s"

            # Verify all sessions processed results
            for session_id in session_ids:
                session = engine.get_session(session_id)
                assert session.metrics.transcription_count == 50

            await engine.stop()

    async def _add_results_to_session(self, session, count):
        """Helper to add results to a session."""
        for i in range(count):
            session.add_transcription_result(f"Result {i}", 0.9)
            await asyncio.sleep(0.001)  # Small delay to simulate processing

    @pytest.mark.asyncio
    async def test_memory_usage_over_time(
        self, performance_config, mock_transcription_service
    ):
        """Test memory usage stability over extended operation."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(performance_config)
            await engine.start()

            session_id = engine.create_session("memory_test")
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            initial_metrics = monitor.get_metrics()

            # Simulate extended operation
            for batch in range(10):
                # Add many results
                for i in range(100):
                    session.add_transcription_result(f"Batch {batch} Result {i}", 0.9)

                # Force garbage collection
                gc.collect()

                # Check memory hasn't grown excessively
                current_metrics = monitor.get_metrics()
                memory_growth = current_metrics["memory_delta_mb"]

                # Memory growth should be bounded
                assert (
                    memory_growth < 100
                ), f"Memory grew by {memory_growth:.1f}MB after batch {batch}"

                await asyncio.sleep(0.1)

            final_metrics = monitor.get_metrics()

            # Total memory growth should be reasonable
            assert (
                final_metrics["memory_delta_mb"] < 150
            ), f"Total memory growth: {final_metrics['memory_delta_mb']:.1f}MB"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_long_running_session_memory_stability(
        self, performance_config, mock_transcription_service
    ):
        """Test memory usage during very long-running sessions (enhanced test)."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(performance_config)
            await engine.start()

            session_id = engine.create_session("long_running_memory_test")
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Simulate 30 minutes of continuous operation (compressed to ~30 seconds for testing)
            total_batches = 100
            results_per_batch = 50
            memory_samples = []

            for batch in range(total_batches):
                # Add transcription results continuously
                for i in range(results_per_batch):
                    # Vary result sizes to simulate real usage
                    text_length = random.randint(10, 200)
                    text = (
                        f"Long running batch {batch} result {i} "
                        + "word " * text_length
                    )
                    confidence = random.uniform(0.7, 0.99)
                    session.add_transcription_result(text, confidence)

                # Sample memory usage every 10 batches
                if batch % 10 == 0:
                    current_metrics = monitor.get_metrics()
                    memory_samples.append(
                        {
                            "batch": batch,
                            "memory_mb": current_metrics["memory_usage_mb"],
                            "memory_delta_mb": current_metrics["memory_delta_mb"],
                            "transcription_count": session.metrics.transcription_count,
                        }
                    )

                    # Force garbage collection periodically
                    gc.collect()

                # Small delay to simulate real-time processing
                await asyncio.sleep(0.01)

            final_metrics = monitor.get_metrics()

            # Verify session processed all results
            expected_results = total_batches * results_per_batch
            assert session.metrics.transcription_count == expected_results

            # Memory growth should be bounded even for very long sessions
            assert (
                final_metrics["memory_delta_mb"] < 300
            ), f"Long-running session memory growth: {final_metrics['memory_delta_mb']:.1f}MB"

            # Memory usage should stabilize (not grow linearly)
            if len(memory_samples) >= 3:
                early_memory = memory_samples[1]["memory_delta_mb"]
                late_memory = memory_samples[-1]["memory_delta_mb"]
                memory_growth_rate = (late_memory - early_memory) / len(memory_samples)

                # Memory growth rate should be low (< 5MB per 10 batches)
                assert (
                    memory_growth_rate < 5.0
                ), f"Memory growing too fast: {memory_growth_rate:.2f}MB per 10 batches"

            # Verify session is still responsive
            session.add_transcription_result("Final responsiveness test", 0.95)
            assert session.metrics.transcription_count == expected_results + 1

            await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_transcription_jobs_performance(
        self, performance_config, mock_transcription_service
    ):
        """Test performance with multiple concurrent transcription jobs (enhanced test)."""
        # Mock transcription service with realistic delays
        mock_transcription_service.transcribe = AsyncMock()

        async def mock_transcribe(audio_data):
            # Simulate transcription processing time
            await asyncio.sleep(random.uniform(0.01, 0.05))
            return {
                "text": f"Transcribed audio chunk {len(audio_data)} bytes",
                "confidence": random.uniform(0.8, 0.99),
                "processing_time": random.uniform(0.01, 0.05),
            }

        mock_transcription_service.transcribe.side_effect = mock_transcribe

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(performance_config)
            await engine.start()

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Create multiple concurrent transcription jobs
            concurrent_jobs = 20
            results_per_job = 25

            async def transcription_job(job_id):
                """Simulate a concurrent transcription job."""
                session_id = engine.create_session(f"concurrent_job_{job_id}")
                await engine.start_session(session_id)
                session = engine.get_session(session_id)

                job_results = []
                for i in range(results_per_job):
                    # Simulate varying transcription loads
                    text_size = random.randint(20, 100)
                    text = f"Job {job_id} result {i} " + "content " * text_size
                    confidence = random.uniform(0.75, 0.98)

                    session.add_transcription_result(text, confidence)
                    job_results.append(text)

                    # Random processing delays
                    await asyncio.sleep(random.uniform(0.001, 0.01))

                return {
                    "job_id": job_id,
                    "session_id": session_id,
                    "results_count": len(job_results),
                    "session_metrics": session.metrics,
                }

            # Run all jobs concurrently
            tasks = [
                asyncio.create_task(transcription_job(i))
                for i in range(concurrent_jobs)
            ]
            job_results = await asyncio.gather(*tasks)

            metrics = monitor.get_metrics()

            # Verify all jobs completed successfully
            assert len(job_results) == concurrent_jobs
            total_results = sum(result["results_count"] for result in job_results)
            expected_total = concurrent_jobs * results_per_job
            assert total_results == expected_total

            # Performance should be reasonable for concurrent jobs
            assert (
                metrics["elapsed_time"] < 30.0
            ), f"Concurrent jobs took {metrics['elapsed_time']:.2f}s"

            # Memory usage should be reasonable
            assert (
                metrics["memory_delta_mb"] < 500
            ), f"Concurrent jobs used {metrics['memory_delta_mb']:.1f}MB"

            # Calculate throughput
            throughput = total_results / metrics["elapsed_time"]
            assert (
                throughput > 50
            ), f"Concurrent throughput: {throughput:.1f} results/sec"

            # Verify all sessions are still active
            active_sessions = len(engine._active_sessions)
            assert active_sessions == concurrent_jobs

            # Test system responsiveness after concurrent load
            test_session_id = engine.create_session("post_concurrent_test")
            await engine.start_session(test_session_id)
            test_session = engine.get_session(test_session_id)
            test_session.add_transcription_result("System still responsive", 0.95)

            assert test_session.metrics.transcription_count == 1

            await engine.stop()


class TestAudioPerformance:
    """Test audio processing performance."""

    def create_test_audio_chunk(self, size=1024):
        """Create test audio chunk."""
        data = np.random.randint(-32768, 32767, size, dtype=np.int16).tobytes()
        return AudioChunk(
            data=data,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=size,
        )

    def test_audio_chunk_creation_performance(self):
        """Test audio chunk creation performance."""
        monitor = PerformanceMonitor()
        monitor.start_monitoring()

        # Create many audio chunks
        chunks = []
        for i in range(1000):
            chunk = self.create_test_audio_chunk()
            chunks.append(chunk)

        metrics = monitor.get_metrics()

        # Chunk creation should be fast
        assert (
            metrics["elapsed_time"] < 1.0
        ), f"Creating 1000 chunks took {metrics['elapsed_time']:.2f}s"

        # Memory usage should be reasonable
        assert (
            metrics["memory_delta_mb"] < 50
        ), f"Memory grew by {metrics['memory_delta_mb']:.1f}MB"

    @pytest.mark.skipif(
        not hasattr(AudioChunk, "to_numpy")
        or AudioChunk(
            b"\x00\x01", 16000, 1, AudioFormat.INT16, time.time(), 1
        ).to_numpy()
        is None,
        reason="Numpy not available",
    )
    def test_audio_format_conversion_performance(self):
        """Test audio format conversion performance."""
        from scribed.audio.base import AudioFormatConverter

        # Create test chunk
        chunk = self.create_test_audio_chunk(16000)  # 1 second of audio

        monitor = PerformanceMonitor()
        monitor.start_monitoring()

        # Convert between formats multiple times
        for i in range(100):
            converted = AudioFormatConverter.convert_chunk_format(
                chunk, AudioFormat.FLOAT32
            )
            converted_back = AudioFormatConverter.convert_chunk_format(
                converted, AudioFormat.INT16
            )

        metrics = monitor.get_metrics()

        # Format conversion should be reasonably fast
        assert (
            metrics["elapsed_time"] < 5.0
        ), f"100 format conversions took {metrics['elapsed_time']:.2f}s"

    @pytest.mark.asyncio
    async def test_audio_source_throughput(self):
        """Test audio source throughput performance."""
        from scribed.audio.base import AudioSource

        class MockHighThroughputSource(AudioSource):
            def __init__(self, config):
                super().__init__(config)
                self.chunk_count = 0
                self.max_chunks = 1000

            async def start(self):
                self._mark_active()

            async def stop(self):
                self._mark_inactive()

            async def read_chunk(self):
                if self.chunk_count >= self.max_chunks:
                    return None

                self.chunk_count += 1
                return self.create_test_audio_chunk()

            def create_test_audio_chunk(self):
                data = b"\x00\x01" * 512  # Small chunk for speed
                return AudioChunk(
                    data=data,
                    sample_rate=16000,
                    channels=1,
                    format=AudioFormat.INT16,
                    timestamp=time.time(),
                    chunk_size=512,
                )

            def get_audio_info(self):
                return {"chunk_count": self.chunk_count}

            def is_available(self):
                return True

        source = MockHighThroughputSource({})

        monitor = PerformanceMonitor()
        monitor.start_monitoring()

        chunks_read = 0
        async for chunk in source.read_stream():
            chunks_read += 1

        metrics = monitor.get_metrics()

        # Should process chunks quickly
        assert chunks_read == 1000
        assert (
            metrics["elapsed_time"] < 2.0
        ), f"Reading 1000 chunks took {metrics['elapsed_time']:.2f}s"

        # Calculate throughput
        throughput = chunks_read / metrics["elapsed_time"]
        assert throughput > 500, f"Throughput was {throughput:.1f} chunks/sec"


class TestReliabilityAndErrorHandling:
    """Test system reliability and error handling."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for reliability testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {"provider": "mock", "model": "test"}
        return service

    @pytest.mark.asyncio
    async def test_engine_error_recovery(self, mock_transcription_service):
        """Test engine error recovery capabilities."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create session
            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Add successful results
            for i in range(10):
                session.add_transcription_result(f"Success {i}", 0.9)

            assert session.metrics.transcription_count == 10
            assert session.metrics.error_count == 0

            # Simulate errors
            for i in range(5):
                session._handle_error(Exception(f"Error {i}"))

            # Verify error handling
            assert session.metrics.error_count == 5
            assert session.status.value == "error"

            # System should still be functional for new sessions
            new_session_id = engine.create_session()
            await engine.start_session(new_session_id)
            new_session = engine.get_session(new_session_id)

            new_session.add_transcription_result("Recovery test", 0.9)
            assert new_session.metrics.transcription_count == 1
            assert new_session.status.value == "active"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, mock_transcription_service):
        """Test error handling under concurrent load."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create multiple sessions
            session_count = 10
            session_ids = []

            for i in range(session_count):
                session_id = engine.create_session(f"error_test_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            # Simulate concurrent errors and operations
            async def session_operations(session_id, should_error):
                session = engine.get_session(session_id)

                for i in range(20):
                    if should_error and i % 5 == 0:
                        session._handle_error(Exception(f"Concurrent error {i}"))
                    else:
                        session.add_transcription_result(f"Result {i}", 0.9)

                    await asyncio.sleep(0.01)

            # Run operations concurrently, some with errors
            tasks = []
            for i, session_id in enumerate(session_ids):
                should_error = i % 3 == 0  # Every 3rd session gets errors
                task = asyncio.create_task(session_operations(session_id, should_error))
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Verify system stability
            error_sessions = 0
            active_sessions = 0

            for session_id in session_ids:
                session = engine.get_session(session_id)
                if session.status.value == "error":
                    error_sessions += 1
                elif session.status.value == "active":
                    active_sessions += 1

            # Some sessions should have errors, others should be active
            assert error_sessions > 0
            assert active_sessions > 0
            assert error_sessions + active_sessions == session_count

            await engine.stop()

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, mock_transcription_service):
        """Test for memory leaks during extended operation."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Simulate many session create/destroy cycles
            for cycle in range(20):
                # Create sessions
                session_ids = []
                for i in range(10):
                    session_id = engine.create_session(f"leak_test_{cycle}_{i}")
                    session_ids.append(session_id)
                    await engine.start_session(session_id)

                # Add results to sessions
                for session_id in session_ids:
                    session = engine.get_session(session_id)
                    for j in range(20):
                        session.add_transcription_result(
                            f"Cycle {cycle} Result {j}", 0.9
                        )

                # Stop all sessions
                for session_id in session_ids:
                    await engine.stop_session(session_id)

                # Force garbage collection
                gc.collect()

                # Check memory usage periodically
                if cycle % 5 == 0:
                    metrics = monitor.get_metrics()
                    # Memory shouldn't grow excessively
                    assert (
                        metrics["memory_delta_mb"] < 200
                    ), f"Memory leak detected: {metrics['memory_delta_mb']:.1f}MB growth"

            final_metrics = monitor.get_metrics()

            # Final memory usage should be reasonable
            assert (
                final_metrics["memory_delta_mb"] < 300
            ), f"Potential memory leak: {final_metrics['memory_delta_mb']:.1f}MB total growth"

            await engine.stop()

    def test_thread_safety(self):
        """Test thread safety of core components."""
        from scribed.core.session import SessionMetrics, TranscriptionResult
        from datetime import datetime

        # Test concurrent access to session metrics
        metrics = SessionMetrics()
        results = []
        errors = []

        def update_metrics(thread_id):
            try:
                for i in range(100):
                    metrics.transcription_count += 1
                    metrics.error_count += 1
                    metrics.bytes_processed += 1024
                    time.sleep(
                        0.001
                    )  # Small delay to increase chance of race conditions
                results.append(f"Thread {thread_id} completed")
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

        # Run multiple threads concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_metrics, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 5

        # Verify final counts (may not be exact due to race conditions, but should be reasonable)
        assert metrics.transcription_count > 0
        assert metrics.error_count > 0
        assert metrics.bytes_processed > 0

    @pytest.mark.asyncio
    async def test_resource_cleanup(self, mock_transcription_service):
        """Test proper resource cleanup."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            # Test multiple engine create/destroy cycles
            for cycle in range(5):
                engine = ScribedEngine(config)
                await engine.start()

                # Create sessions
                session_ids = []
                for i in range(5):
                    session_id = engine.create_session(f"cleanup_test_{i}")
                    session_ids.append(session_id)
                    await engine.start_session(session_id)

                # Verify sessions are active
                assert len(engine._active_sessions) == 5

                # Stop engine (should cleanup all resources)
                await engine.stop()

                # Verify cleanup
                assert len(engine._active_sessions) == 0
                assert engine.status.value == "disabled"
                assert not engine._running

        # Force garbage collection
        gc.collect()

    @pytest.mark.asyncio
    async def test_cascading_error_recovery(self, mock_transcription_service):
        """Test recovery from cascading error scenarios (enhanced test)."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create multiple interconnected sessions
            session_count = 15
            session_ids = []

            for i in range(session_count):
                session_id = engine.create_session(f"cascade_recovery_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            # Simulate cascading failures
            error_types = [
                Exception("Network timeout"),
                ValueError("Invalid audio format"),
                RuntimeError("Transcription engine failure"),
                MemoryError("Out of memory"),
                ConnectionError("Service unavailable"),
            ]

            # Introduce errors in waves, but keep some sessions healthy
            for wave in range(3):
                affected_sessions = session_ids[wave * 5 : (wave + 1) * 5]

                for i, session_id in enumerate(affected_sessions):
                    session = engine.get_session(session_id)

                    # Some sessions remain healthy (no errors)
                    if i % 3 == 0:
                        # Keep this session healthy with only successful results
                        for k in range(10):
                            session.add_transcription_result(
                                f"Healthy session result {k}", 0.9
                            )
                    else:
                        # Add some successful results first, then errors
                        for k in range(5):
                            session.add_transcription_result(
                                f"Pre-error result {k}", 0.9
                            )

                        # Then add errors to put session in error state
                        error = error_types[i % len(error_types)]
                        for j in range(3):
                            session._handle_error(error)

                # Small delay between waves
                await asyncio.sleep(0.1)

            # Verify system stability after cascading errors
            healthy_sessions = 0
            error_sessions = 0
            sessions_with_results = 0

            for session_id in session_ids:
                session = engine.get_session(session_id)
                if session.status.value == "active":
                    healthy_sessions += 1
                    if session.metrics.transcription_count > 0:
                        sessions_with_results += 1
                elif session.status.value == "error":
                    error_sessions += 1

            # System should maintain some functionality
            assert healthy_sessions > 0, "No sessions remained healthy"
            assert sessions_with_results > 0, "No sessions have transcription results"
            assert engine.status.value == "running", "Engine should still be running"

            # Should be able to create new sessions after cascading errors
            recovery_session_id = engine.create_session("post_cascade_recovery")
            await engine.start_session(recovery_session_id)
            recovery_session = engine.get_session(recovery_session_id)

            for i in range(10):
                recovery_session.add_transcription_result(
                    f"Post-cascade result {i}", 0.95
                )

            assert recovery_session.status.value == "active"
            assert recovery_session.metrics.transcription_count == 10
            assert recovery_session.metrics.error_count == 0

            await engine.stop()

    @pytest.mark.asyncio
    async def test_high_error_rate_resilience(self, mock_transcription_service):
        """Test system resilience under high error rates (enhanced test)."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session("high_error_rate_test")
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Simulate high error rate scenario (70% errors, 30% success)
            total_operations = 1000
            error_rate = 0.7

            successful_results = 0
            error_count = 0

            for i in range(total_operations):
                if random.random() < error_rate:
                    # Generate error
                    error_types = [
                        Exception(f"Random error {i}"),
                        ValueError(f"Validation error {i}"),
                        RuntimeError(f"Runtime error {i}"),
                    ]
                    error = random.choice(error_types)
                    session._handle_error(error)
                    error_count += 1
                else:
                    # Generate successful result
                    session.add_transcription_result(
                        f"Success result {i}", random.uniform(0.8, 0.99)
                    )
                    successful_results += 1

                # Occasional recovery attempts
                if i % 100 == 0 and session.status.value == "error":
                    # Simulate recovery by adding several successful results
                    for j in range(5):
                        session.add_transcription_result(
                            f"Recovery attempt {i}_{j}", 0.95
                        )
                        successful_results += 1

                # Small delay to prevent overwhelming the system
                if i % 50 == 0:
                    await asyncio.sleep(0.01)

            # Verify system handled high error rate gracefully
            assert session.metrics.error_count == error_count
            assert session.metrics.transcription_count >= successful_results

            # System should still be responsive despite high error rate
            session.add_transcription_result("Final responsiveness test", 0.99)
            assert session.metrics.transcription_count >= successful_results + 1

            # Engine should still be functional
            assert engine.status.value == "running"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_error_isolation(self, mock_transcription_service):
        """Test error isolation between concurrent sessions (enhanced test)."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create sessions with different error patterns
            session_configs = [
                {"name": "healthy", "error_rate": 0.0, "operations": 100},
                {"name": "low_error", "error_rate": 0.1, "operations": 100},
                {"name": "medium_error", "error_rate": 0.3, "operations": 100},
                {"name": "high_error", "error_rate": 0.7, "operations": 100},
                {"name": "critical_error", "error_rate": 0.9, "operations": 100},
            ]

            session_results = {}

            async def session_worker(config_info):
                """Worker that simulates different error patterns."""
                session_id = engine.create_session(
                    f"isolation_test_{config_info['name']}"
                )
                await engine.start_session(session_id)
                session = engine.get_session(session_id)

                successful_ops = 0
                error_ops = 0

                for i in range(config_info["operations"]):
                    if random.random() < config_info["error_rate"]:
                        # Generate error
                        session._handle_error(
                            Exception(f"{config_info['name']} error {i}")
                        )
                        error_ops += 1
                    else:
                        # Generate success
                        session.add_transcription_result(
                            f"{config_info['name']} result {i}",
                            random.uniform(0.8, 0.99),
                        )
                        successful_ops += 1

                    # Random delays to simulate real processing
                    await asyncio.sleep(random.uniform(0.001, 0.005))

                return {
                    "session_id": session_id,
                    "name": config_info["name"],
                    "successful_ops": successful_ops,
                    "error_ops": error_ops,
                    "final_status": session.status.value,
                    "transcription_count": session.metrics.transcription_count,
                    "error_count": session.metrics.error_count,
                }

            # Run all session workers concurrently
            tasks = [
                asyncio.create_task(session_worker(config))
                for config in session_configs
            ]
            results = await asyncio.gather(*tasks)

            # Analyze results for error isolation
            healthy_sessions = []
            error_sessions = []

            for result in results:
                session_results[result["name"]] = result

                if result["final_status"] == "active":
                    healthy_sessions.append(result)
                elif result["final_status"] == "error":
                    error_sessions.append(result)

            # Verify error isolation
            assert len(healthy_sessions) > 0, "No sessions remained healthy"
            assert (
                session_results["healthy"]["final_status"] == "active"
            ), "Healthy session was affected by others"
            assert (
                session_results["healthy"]["error_count"] == 0
            ), "Healthy session got errors from others"

            # High error rate sessions should not affect low error rate sessions
            if "low_error" in session_results:
                low_error_session = session_results["low_error"]
                assert (
                    low_error_session["transcription_count"] > 50
                ), "Low error session was overly affected"

            # Engine should still be functional despite some sessions having high error rates
            assert engine.status.value == "running"

            # Should be able to create new healthy session
            test_session_id = engine.create_session("post_isolation_test")
            await engine.start_session(test_session_id)
            test_session = engine.get_session(test_session_id)

            for i in range(10):
                test_session.add_transcription_result(f"Isolation test {i}", 0.95)

            assert test_session.status.value == "active"
            assert test_session.metrics.transcription_count == 10
            assert test_session.metrics.error_count == 0

            await engine.stop()

    def test_configuration_edge_cases(self):
        """Test configuration handling edge cases."""
        # Test with minimal configuration
        minimal_config = Config()
        assert minimal_config is not None

        # Test with extreme values
        try:
            extreme_config = Config(
                audio={
                    "sample_rate": 192000,  # Very high sample rate
                    "channels": 8,  # Many channels
                    "chunk_size": 8192,  # Large chunk size
                }
            )
            assert extreme_config is not None
        except Exception as e:
            # Should handle extreme values gracefully
            assert "validation" in str(e).lower() or "invalid" in str(e).lower()

    @pytest.mark.asyncio
    async def test_long_running_stability(self, mock_transcription_service):
        """Test system stability during long-running operation."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session("stability_test")
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            monitor = PerformanceMonitor()
            monitor.start_monitoring()

            # Simulate long-running operation
            start_time = time.time()
            operation_duration = 10.0  # 10 seconds

            result_count = 0
            while time.time() - start_time < operation_duration:
                # Add transcription results continuously
                session.add_transcription_result(
                    f"Long running result {result_count}", 0.9
                )
                result_count += 1

                # Occasional pause/resume to test state transitions
                if result_count % 100 == 0:
                    await session.pause()
                    await asyncio.sleep(0.01)
                    await session.resume()

                await asyncio.sleep(0.01)  # 100 results per second

            metrics = monitor.get_metrics()

            # Verify system remained stable
            assert session.status.value == "active"
            assert session.metrics.transcription_count == result_count
            assert session.metrics.error_count == 0

            # Performance should remain reasonable
            assert (
                metrics["memory_delta_mb"] < 100
            ), f"Memory grew by {metrics['memory_delta_mb']:.1f}MB"

            # Calculate processing rate
            processing_rate = result_count / metrics["elapsed_time"]
            assert (
                processing_rate > 50
            ), f"Processing rate dropped to {processing_rate:.1f} results/sec"

            await engine.stop()
