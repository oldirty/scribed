"""Audio preprocessing for noise reduction and volume normalization."""

import logging
import numpy as np
from typing import Optional, Dict, Any
from scipy import signal
from scipy.ndimage import median_filter
import librosa


class AudioPreprocessor:
    """Audio preprocessing pipeline for noise reduction and normalization."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize audio preprocessor.

        Args:
            config: Configuration dictionary with preprocessing options:
                - enabled: Enable/disable preprocessing (default: True)
                - volume_normalization: Enable volume normalization (default: True)
                - noise_reduction: Enable noise reduction (default: True)
                - target_db: Target RMS level in dB (default: -20)
                - noise_gate_threshold: Noise gate threshold in dB (default: -40)
                - spectral_gating: Enable spectral gating noise reduction (default: True)
                - high_pass_cutoff: High-pass filter cutoff frequency (default: 85)
                - low_pass_cutoff: Low-pass filter cutoff frequency (default: None)
        """
        self.logger = logging.getLogger(__name__)
        
        self.enabled = config.get("enabled", True)
        self.volume_normalization = config.get("volume_normalization", True)
        self.noise_reduction = config.get("noise_reduction", True)
        self.target_db = config.get("target_db", -20.0)
        self.noise_gate_threshold = config.get("noise_gate_threshold", -40.0)
        self.spectral_gating = config.get("spectral_gating", True)
        self.high_pass_cutoff = config.get("high_pass_cutoff", 85)
        self.low_pass_cutoff = config.get("low_pass_cutoff", None)
        
        # Internal state for adaptive processing
        self._noise_profile: Optional[np.ndarray] = None
        self._noise_estimation_frames = 0
        self._max_noise_frames = 50  # Frames to collect for noise profile
        
        self.logger.info(f"Audio preprocessor initialized - Enabled: {self.enabled}")
        if self.enabled:
            self.logger.info(f"Volume normalization: {self.volume_normalization}")
            self.logger.info(f"Noise reduction: {self.noise_reduction}")
            self.logger.info(f"Target level: {self.target_db} dB")

    def process_audio(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Process audio data through preprocessing pipeline.

        Args:
            audio_data: Raw audio data as numpy array
            sample_rate: Sample rate in Hz

        Returns:
            Processed audio data
        """
        if not self.enabled or len(audio_data) == 0:
            return audio_data

        try:
            # Ensure audio is float32 for processing
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalize to [-1, 1] range
            if audio_data.dtype == np.int16:
                audio_data = audio_data / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data / 2147483648.0

            processed_audio = audio_data.copy()

            # 1. High-pass filter to remove low-frequency noise
            if self.high_pass_cutoff:
                processed_audio = self._apply_high_pass_filter(
                    processed_audio, sample_rate, self.high_pass_cutoff
                )

            # 2. Low-pass filter if configured
            if self.low_pass_cutoff:
                processed_audio = self._apply_low_pass_filter(
                    processed_audio, sample_rate, self.low_pass_cutoff
                )

            # 3. Noise reduction
            if self.noise_reduction:
                processed_audio = self._reduce_noise(processed_audio, sample_rate)

            # 4. Noise gate
            processed_audio = self._apply_noise_gate(processed_audio)

            # 5. Volume normalization
            if self.volume_normalization:
                processed_audio = self._normalize_volume(processed_audio)

            return processed_audio

        except Exception as e:
            self.logger.warning(f"Audio preprocessing failed: {e}")
            return audio_data  # Return original audio on error

    def _apply_high_pass_filter(self, audio: np.ndarray, sample_rate: int, cutoff: float) -> np.ndarray:
        """Apply high-pass filter to remove low-frequency noise."""
        try:
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff / nyquist
            
            # Design Butterworth high-pass filter
            b, a = signal.butter(4, normalized_cutoff, btype='high', analog=False)
            filtered_audio = signal.filtfilt(b, a, audio)
            
            return filtered_audio.astype(np.float32)
        except Exception as e:
            self.logger.warning(f"High-pass filter failed: {e}")
            return audio

    def _apply_low_pass_filter(self, audio: np.ndarray, sample_rate: int, cutoff: float) -> np.ndarray:
        """Apply low-pass filter to remove high-frequency noise."""
        try:
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff / nyquist
            
            # Design Butterworth low-pass filter
            b, a = signal.butter(4, normalized_cutoff, btype='low', analog=False)
            filtered_audio = signal.filtfilt(b, a, audio)
            
            return filtered_audio.astype(np.float32)
        except Exception as e:
            self.logger.warning(f"Low-pass filter failed: {e}")
            return audio

    def _reduce_noise(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply noise reduction using spectral gating."""
        if not self.spectral_gating:
            return audio

        try:
            # Use librosa for spectral processing
            # Compute spectral magnitude
            stft = librosa.stft(audio, n_fft=2048, hop_length=512)
            magnitude = np.abs(stft)
            phase = np.angle(stft)

            # Update noise profile if still collecting
            if self._noise_estimation_frames < self._max_noise_frames:
                self._update_noise_profile(magnitude)
                self._noise_estimation_frames += 1

            # Apply spectral gating if we have a noise profile
            if self._noise_profile is not None:
                # Calculate gain for each frequency bin
                gain = self._calculate_spectral_gain(magnitude)
                
                # Apply gain to magnitude
                processed_magnitude = magnitude * gain
                
                # Reconstruct audio
                processed_stft = processed_magnitude * np.exp(1j * phase)
                processed_audio = librosa.istft(processed_stft, hop_length=512)
                
                return processed_audio.astype(np.float32)

            return audio

        except Exception as e:
            self.logger.warning(f"Spectral noise reduction failed: {e}")
            return audio

    def _update_noise_profile(self, magnitude: np.ndarray) -> None:
        """Update noise profile with new magnitude spectrum."""
        # Use median to estimate noise floor
        frame_noise = np.median(magnitude, axis=1)
        
        if self._noise_profile is None:
            self._noise_profile = frame_noise
        else:
            # Exponential moving average
            alpha = 0.1
            self._noise_profile = alpha * frame_noise + (1 - alpha) * self._noise_profile

    def _calculate_spectral_gain(self, magnitude: np.ndarray) -> np.ndarray:
        """Calculate gain for spectral gating."""
        if self._noise_profile is None:
            return np.ones_like(magnitude)

        # Calculate SNR for each frequency bin
        snr = magnitude / (self._noise_profile[:, np.newaxis] + 1e-10)
        
        # Apply gain based on SNR
        # Higher SNR = more gain (preserve signal)
        # Lower SNR = less gain (reduce noise)
        snr_db = 20 * np.log10(snr + 1e-10)
        
        # Sigmoid-like gain function
        gain_threshold = 6.0  # dB above noise floor
        gain = 1 / (1 + np.exp(-(snr_db - gain_threshold) / 3.0))
        
        # Ensure minimum gain to avoid artifacts
        gain = np.maximum(gain, 0.1)
        
        return gain

    def _apply_noise_gate(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise gate to silence low-level noise."""
        try:
            # Calculate RMS in overlapping windows
            window_size = 1024
            hop_size = 512
            
            if len(audio) < window_size:
                # For short audio, just apply threshold to whole signal
                rms = np.sqrt(np.mean(audio ** 2))
                rms_db = 20 * np.log10(rms + 1e-10)
                
                if rms_db < self.noise_gate_threshold:
                    return audio * 0.1  # Reduce but don't completely silence
                return audio

            # Process in windows
            processed_audio = audio.copy()
            
            for i in range(0, len(audio) - window_size, hop_size):
                window = audio[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                rms_db = 20 * np.log10(rms + 1e-10)
                
                if rms_db < self.noise_gate_threshold:
                    # Apply aggressive reduction but not complete silence
                    processed_audio[i:i + window_size] *= 0.1

            return processed_audio

        except Exception as e:
            self.logger.warning(f"Noise gate failed: {e}")
            return audio

    def _normalize_volume(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio volume to target level."""
        try:
            # Calculate RMS
            rms = np.sqrt(np.mean(audio ** 2))
            
            if rms < 1e-10:  # Avoid division by zero
                return audio

            # Calculate target RMS from dB
            target_rms = 10 ** (self.target_db / 20.0)
            
            # Calculate gain
            gain = target_rms / rms
            
            # Limit gain to prevent clipping and distortion
            max_gain = 10.0  # Maximum 20dB boost
            gain = min(gain, max_gain)
            
            # Apply gain
            normalized_audio = audio * gain
            
            # Ensure no clipping
            max_val = np.max(np.abs(normalized_audio))
            if max_val > 0.95:
                normalized_audio = normalized_audio * (0.95 / max_val)

            return normalized_audio

        except Exception as e:
            self.logger.warning(f"Volume normalization failed: {e}")
            return audio

    def reset_noise_profile(self) -> None:
        """Reset the noise profile to re-learn background noise."""
        self._noise_profile = None
        self._noise_estimation_frames = 0
        self.logger.info("Noise profile reset")

    @staticmethod
    def is_available() -> bool:
        """Check if audio preprocessing dependencies are available."""
        try:
            import scipy
            import librosa
            return True
        except ImportError:
            return False

    def get_config(self) -> Dict[str, Any]:
        """Get current preprocessor configuration."""
        return {
            "enabled": self.enabled,
            "volume_normalization": self.volume_normalization,
            "noise_reduction": self.noise_reduction,
            "target_db": self.target_db,
            "noise_gate_threshold": self.noise_gate_threshold,
            "spectral_gating": self.spectral_gating,
            "high_pass_cutoff": self.high_pass_cutoff,
            "low_pass_cutoff": self.low_pass_cutoff,
        }
