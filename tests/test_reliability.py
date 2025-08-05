"""Reliability and stress tests for Scribed components."""

import pytest
import asyncio
import time
import threading
import random
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile

import numpy as np

from scribed.core.engine import ScribedEngine, EngineStatus
from scribed.core.session import TranscriptionSession, SessionStatus
from scribed.config import Config
from scribed.audio.base import AudioChunk, AudioFormat, AudioError
from scribed.transcription.service import TranscriptionService


class TestStressScenarios:
    """Test system behavior under stress conditions."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for stress testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {
            "provider": "mock",
            "model": "stress_test",
        }
        return service

    @pytest.mark.asyncio
    async def test_rapid_session_creation_destruction(self, mock_transcription_service):
        """Test rapid session creation and destruction."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Rapidly create and destroy sessions
            for cycle in range(50):
                session_ids = []

                # Create multiple sessions
                for i in range(10):
                    session_id = engine.create_session(f"stress_{cycle}_{i}")
                    session_ids.append(session_id)
                    await engine.start_session(session_id)

                # Verify all sessions are active
                assert len(engine._active_sessions) == 10

                # Add some results
                for session_id in session_ids:
                    session = engine.get_session(session_id)
                    session.add_transcription_result(f"Stress test {cycle}", 0.9)

                # Destroy all sessions
                for session_id in session_ids:
                    await engine.stop_session(session_id)

                # Verify cleanup
                assert len(engine._active_sessions) == 0

                # Occasional garbage collection
                if cycle % 10 == 0:
                    gc.collect()

            await engine.stop()

    @pytest.mark.asyncio
    async def test_high_volume_transcription_results(self, mock_transcription_service):
        """Test handling high volume of transcription results."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session("high_volume")
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Add large number of results rapidly
            result_count = 10000
            start_time = time.time()

            for i in range(result_count):
                # Mix of partial and final results
                is_partial = i % 5 != 0  # Every 5th result is final
                session.add_transcription_result(
                    f"High volume result {i}",
                    confidence=random.uniform(0.7, 0.99),
                    is_partial=is_partial,
                )

                # Occasional async yield to prevent blocking
                if i % 100 == 0:
                    await asyncio.sleep(0.001)

            end_time = time.time()
            processing_time = end_time - start_time

            # Verify all results were processed
            all_results = session.get_results(include_partial=True)
            final_results = session.get_results(include_partial=False)

            assert len(all_results) == result_count
            assert len(final_results) == result_count // 5  # Every 5th was final
            assert session.metrics.transcription_count == len(final_results)

            # Performance should be reasonable
            results_per_second = result_count / processing_time
            assert (
                results_per_second > 1000
            ), f"Processing rate: {results_per_second:.1f} results/sec"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, mock_transcription_service):
        """Test concurrent operations across multiple sessions."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create multiple sessions
            session_count = 20
            session_ids = []

            for i in range(session_count):
                session_id = engine.create_session(f"concurrent_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            async def session_worker(session_id, worker_id):
                """Worker function for concurrent session operations."""
                session = engine.get_session(session_id)
                operations = 0

                for i in range(100):
                    # Random operations
                    operation = random.choice(
                        ["add_result", "pause", "resume", "get_status"]
                    )

                    try:
                        if operation == "add_result":
                            session.add_transcription_result(
                                f"Worker {worker_id} result {i}", 0.9
                            )
                            operations += 1
                        elif (
                            operation == "pause"
                            and session.status == SessionStatus.ACTIVE
                        ):
                            await session.pause()
                            operations += 1
                        elif (
                            operation == "resume"
                            and session.status == SessionStatus.PAUSED
                        ):
                            await session.resume()
                            operations += 1
                        elif operation == "get_status":
                            status = session.get_status_info()
                            assert status is not None
                            operations += 1

                        # Small random delay
                        await asyncio.sleep(random.uniform(0.001, 0.01))

                    except Exception as e:
                        # Log but don't fail - some operations may conflict
                        print(f"Worker {worker_id} operation {operation} failed: {e}")

                return operations

            # Run concurrent workers
            tasks = []
            for i, session_id in enumerate(session_ids):
                task = asyncio.create_task(session_worker(session_id, i))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify workers completed successfully
            successful_operations = 0
            for result in results:
                if isinstance(result, int):
                    successful_operations += result
                else:
                    print(f"Worker failed: {result}")

            assert (
                successful_operations > 1000
            ), f"Only {successful_operations} operations completed"

            # Verify system is still functional
            assert len(engine._active_sessions) == session_count

            await engine.stop()

    def test_memory_pressure_handling(self):
        """Test system behavior under memory pressure."""
        # Create large objects to simulate memory pressure
        large_objects = []

        try:
            # Allocate memory in chunks
            for i in range(100):
                # Create 10MB chunks
                chunk = np.zeros(10 * 1024 * 1024 // 8, dtype=np.float64)  # 10MB
                large_objects.append(chunk)

                # Test basic functionality under memory pressure
                config = Config()
                assert config is not None

                # Create audio chunk
                audio_data = b"\x00\x01" * 1024
                chunk = AudioChunk(
                    data=audio_data,
                    sample_rate=16000,
                    channels=1,
                    format=AudioFormat.INT16,
                    timestamp=time.time(),
                    chunk_size=1024,
                )
                assert chunk is not None

                # Force garbage collection periodically
                if i % 10 == 0:
                    gc.collect()

        except MemoryError:
            # Expected under extreme memory pressure
            pass
        finally:
            # Cleanup
            large_objects.clear()
            gc.collect()

    @pytest.mark.asyncio
    async def test_error_cascade_prevention(self, mock_transcription_service):
        """Test prevention of error cascades."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create multiple sessions
            session_ids = []
            for i in range(10):
                session_id = engine.create_session(f"cascade_test_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            # Introduce errors in some sessions
            error_sessions = session_ids[:5]  # First 5 sessions get errors
            healthy_sessions = session_ids[5:]  # Last 5 remain healthy

            # Trigger errors in error sessions
            for session_id in error_sessions:
                session = engine.get_session(session_id)
                for i in range(10):
                    session._handle_error(Exception(f"Cascade test error {i}"))

            # Continue normal operations in healthy sessions
            for session_id in healthy_sessions:
                session = engine.get_session(session_id)
                for i in range(20):
                    session.add_transcription_result(f"Healthy result {i}", 0.9)

            # Verify error isolation
            for session_id in error_sessions:
                session = engine.get_session(session_id)
                assert session.status == SessionStatus.ERROR
                assert session.metrics.error_count >= 10

            for session_id in healthy_sessions:
                session = engine.get_session(session_id)
                assert session.status == SessionStatus.ACTIVE
                assert session.metrics.error_count == 0
                assert session.metrics.transcription_count == 20

            # Engine should still be functional
            assert engine.status == EngineStatus.RUNNING

            # Should be able to create new sessions
            new_session_id = engine.create_session("post_error_test")
            await engine.start_session(new_session_id)
            new_session = engine.get_session(new_session_id)
            new_session.add_transcription_result("Recovery test", 0.9)

            assert new_session.status == SessionStatus.ACTIVE
            assert new_session.metrics.transcription_count == 1

            await engine.stop()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for edge case testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {
            "provider": "mock",
            "model": "edge_test",
        }
        return service

    @pytest.mark.asyncio
    async def test_empty_transcription_results(self, mock_transcription_service):
        """Test handling of empty transcription results."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Test empty text
            session.add_transcription_result("", 0.9)
            session.add_transcription_result("   ", 0.8)  # Whitespace only
            session.add_transcription_result("Valid text", 0.95)

            results = session.get_results()
            assert len(results) == 3

            # All results should be stored, even empty ones
            assert results[0].text == ""
            assert results[1].text == "   "
            assert results[2].text == "Valid text"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_extreme_confidence_values(self, mock_transcription_service):
        """Test handling of extreme confidence values."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Test extreme confidence values
            extreme_values = [-1.0, 0.0, 1.0, 2.0, float("inf"), float("-inf")]

            for i, confidence in enumerate(extreme_values):
                try:
                    session.add_transcription_result(f"Test {i}", confidence)
                except Exception as e:
                    # Some extreme values might be rejected
                    print(f"Confidence {confidence} rejected: {e}")

            # Should handle at least the valid range
            session.add_transcription_result("Valid low", 0.1)
            session.add_transcription_result("Valid high", 0.99)

            results = session.get_results()
            assert len(results) >= 2  # At least the valid ones

            await engine.stop()

    @pytest.mark.asyncio
    async def test_very_long_transcription_text(self, mock_transcription_service):
        """Test handling of very long transcription text."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Create very long text
            long_text = "This is a very long transcription result. " * 1000  # ~43KB
            very_long_text = "Extremely long text. " * 10000  # ~220KB

            session.add_transcription_result(long_text, 0.9)
            session.add_transcription_result(very_long_text, 0.8)

            results = session.get_results()
            assert len(results) == 2
            assert len(results[0].text) > 40000
            assert len(results[1].text) > 200000

            # Final text should combine both
            final_text = session.get_final_text()
            assert len(final_text) > 240000

            await engine.stop()

    @pytest.mark.asyncio
    async def test_rapid_state_transitions(self, mock_transcription_service):
        """Test rapid session state transitions."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Rapid state transitions
            for i in range(100):
                await session.pause()
                assert session.status == SessionStatus.PAUSED

                await session.resume()
                assert session.status == SessionStatus.ACTIVE

                # Add result during active state
                session.add_transcription_result(f"Rapid transition {i}", 0.9)

            # Verify final state
            assert session.status == SessionStatus.ACTIVE
            assert session.metrics.transcription_count == 100

            await engine.stop()

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        from scribed.core.session import TranscriptionResult
        from datetime import datetime

        # Test various Unicode characters
        unicode_texts = [
            "Hello 世界",  # Chinese
            "Здравствуй мир",  # Russian
            "مرحبا بالعالم",  # Arabic
            "🎵 Music notes 🎶",  # Emojis
            "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?",
            "\n\t\r Line breaks and tabs",
            "Zero width: \u200b\u200c\u200d",  # Zero-width characters
        ]

        for text in unicode_texts:
            result = TranscriptionResult(
                text=text, confidence=0.9, timestamp=datetime.now()
            )

            assert result.text == text
            assert len(result.text) >= 0

    @pytest.mark.asyncio
    async def test_session_lifecycle_edge_cases(self, mock_transcription_service):
        """Test session lifecycle edge cases."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            session = engine.get_session(session_id)

            # Test operations on non-started session
            session.add_transcription_result("Before start", 0.9)  # Should be ignored
            assert session.metrics.transcription_count == 0

            # Start session
            await engine.start_session(session_id)

            # Test double start
            await engine.start_session(session_id)  # Should not error
            assert session.status == SessionStatus.ACTIVE

            # Test pause when not active
            await session.stop()
            await session.pause()  # Should not error

            # Test resume when not paused
            await engine.start_session(session_id)
            await session.resume()  # Should not error

            await engine.stop()

    def test_audio_chunk_edge_cases(self):
        """Test audio chunk handling edge cases."""
        # Test minimum size chunk
        tiny_chunk = AudioChunk(
            data=b"\x00\x01",  # 2 bytes
            sample_rate=8000,  # Minimum reasonable sample rate
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=1,
        )
        assert tiny_chunk.duration_seconds > 0

        # Test large chunk
        large_data = b"\x00\x01" * 100000  # 200KB
        large_chunk = AudioChunk(
            data=large_data,
            sample_rate=48000,
            channels=2,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100000,
        )
        assert large_chunk.duration_seconds > 0

        # Test different formats
        formats = [AudioFormat.INT16, AudioFormat.INT32, AudioFormat.FLOAT32]
        for fmt in formats:
            chunk = AudioChunk(
                data=b"\x00\x01\x02\x03" * 100,
                sample_rate=16000,
                channels=1,
                format=fmt,
                timestamp=time.time(),
                chunk_size=100,
            )
            assert chunk._get_bytes_per_sample() > 0

    @pytest.mark.asyncio
    async def test_callback_exception_handling(self, mock_transcription_service):
        """Test callback exception handling."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Add callbacks that raise exceptions
            def bad_result_callback(result):
                raise Exception("Result callback error")

            def bad_status_callback(old_status, new_status):
                raise Exception("Status callback error")

            def bad_error_callback(error):
                raise Exception("Error callback error")

            session.add_result_callback(bad_result_callback)
            session.add_status_callback(bad_status_callback)
            session.add_error_callback(bad_error_callback)

            # Operations should continue despite callback errors
            session.add_transcription_result("Test with bad callbacks", 0.9)
            assert session.metrics.transcription_count == 1

            await session.pause()
            await session.resume()

            session._handle_error(Exception("Test error"))
            assert session.metrics.error_count == 1

            await engine.stop()


class TestRecoveryScenarios:
    """Test system recovery from various failure scenarios."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for recovery testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {
            "provider": "mock",
            "model": "recovery_test",
        }
        return service

    @pytest.mark.asyncio
    async def test_transcription_service_failure_recovery(self):
        """Test recovery from transcription service failures."""
        config = Config()

        # Start with working service
        working_service = Mock(spec=TranscriptionService)
        working_service.is_available.return_value = True
        working_service.get_engine_info.return_value = {"provider": "working"}

        with patch(
            "scribed.core.engine.TranscriptionService", return_value=working_service
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Simulate service failure
            working_service.is_available.return_value = False

            # Engine should detect the failure
            assert not engine.is_healthy()

            # Simulate service recovery
            working_service.is_available.return_value = True

            # Engine should recover
            assert engine.is_healthy()

            await engine.stop()

    @pytest.mark.asyncio
    async def test_partial_system_failure_recovery(self, mock_transcription_service):
        """Test recovery from partial system failures."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Create multiple sessions
            session_ids = []
            for i in range(5):
                session_id = engine.create_session(f"recovery_test_{i}")
                session_ids.append(session_id)
                await engine.start_session(session_id)

            # Simulate failure in some sessions
            failed_sessions = session_ids[:2]
            working_sessions = session_ids[2:]

            for session_id in failed_sessions:
                session = engine.get_session(session_id)
                session._handle_error(Exception("Simulated failure"))

            # Working sessions should continue to function
            for session_id in working_sessions:
                session = engine.get_session(session_id)
                session.add_transcription_result("Recovery test", 0.9)
                assert session.status == SessionStatus.ACTIVE

            # Should be able to create new sessions
            new_session_id = engine.create_session("post_failure")
            await engine.start_session(new_session_id)
            new_session = engine.get_session(new_session_id)
            new_session.add_transcription_result("New session works", 0.9)

            assert new_session.status == SessionStatus.ACTIVE
            assert new_session.metrics.transcription_count == 1

            await engine.stop()

    @pytest.mark.asyncio
    async def test_resource_exhaustion_recovery(self, mock_transcription_service):
        """Test recovery from resource exhaustion scenarios."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            # Simulate resource exhaustion by creating many sessions
            session_ids = []
            try:
                for i in range(1000):  # Try to create many sessions
                    session_id = engine.create_session(f"exhaustion_test_{i}")
                    session_ids.append(session_id)
                    await engine.start_session(session_id)

                    # Add some load to each session
                    session = engine.get_session(session_id)
                    for j in range(10):
                        session.add_transcription_result(f"Load test {j}", 0.9)

                    # Check if we should stop (simulating resource limits)
                    if i > 100 and len(engine._active_sessions) > 100:
                        break

            except Exception as e:
                # Expected under resource exhaustion
                print(f"Resource exhaustion at {len(session_ids)} sessions: {e}")

            # System should still be responsive
            assert engine.status == EngineStatus.RUNNING

            # Clean up some sessions to free resources
            cleanup_count = min(50, len(session_ids))
            for session_id in session_ids[:cleanup_count]:
                await engine.stop_session(session_id)

            # Should be able to create new sessions after cleanup
            recovery_session_id = engine.create_session("recovery_session")
            await engine.start_session(recovery_session_id)
            recovery_session = engine.get_session(recovery_session_id)
            recovery_session.add_transcription_result("Recovery successful", 0.9)

            assert recovery_session.status == SessionStatus.ACTIVE

            await engine.stop()

    def test_configuration_corruption_recovery(self):
        """Test recovery from configuration corruption."""
        # Test with various corrupted configurations
        corrupted_configs = [
            {},  # Empty config
            {"invalid": "structure"},  # Invalid structure
            {"audio": {"sample_rate": -1}},  # Invalid values
        ]

        for corrupted_config in corrupted_configs:
            try:
                # Should either create valid config with defaults or raise clear error
                if corrupted_config:
                    config = Config(**corrupted_config)
                else:
                    config = Config()

                # Basic functionality should work
                assert config is not None

            except Exception as e:
                # Should raise clear, specific errors
                assert len(str(e)) > 0
                print(f"Config {corrupted_config} properly rejected: {e}")

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, mock_transcription_service):
        """Test graceful degradation under adverse conditions."""
        config = Config()

        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)
            session = engine.get_session(session_id)

            # Simulate degraded conditions
            degradation_scenarios = [
                (
                    "High error rate",
                    lambda: session._handle_error(Exception("Degraded error")),
                ),
                (
                    "Low confidence results",
                    lambda: session.add_transcription_result("Low conf", 0.1),
                ),
                ("Slow processing", lambda: time.sleep(0.01)),
            ]

            for scenario_name, scenario_func in degradation_scenarios:
                print(f"Testing {scenario_name}")

                # Apply degradation
                for i in range(10):
                    scenario_func()
                    # System should remain responsive
                    status = session.get_status_info()
                    assert status is not None

                # Add normal result to verify system still works
                session.add_transcription_result(f"Normal after {scenario_name}", 0.9)

            # Verify system maintained basic functionality
            results = session.get_results()
            normal_results = [r for r in results if r.confidence > 0.8]
            assert len(normal_results) >= 3  # At least one per scenario

            await engine.stop()
