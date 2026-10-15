import threading
import time

import numpy as np
import sounddevice as sd

from faster_whisper import WhisperModel
import pyttsx3

from PySide6.QtCore import QThread, Signal


class VoiceEngine:
    """
    Handles:
    - Microphone recording
    - Local Whisper speech-to-text
    - Automatic end-of-speech detection
    - Offline Windows text-to-speech
    - Stopping active speech
    - Stopping microphone recording early
    """

    def __init__(
        self,
        model_size="tiny.en",
        sample_rate=16000,
        record_seconds=30,
        silence_threshold=0.015,
        silence_duration=1.2,
        minimum_record_seconds=0.5,
    ):
        self.model_size = model_size
        self.sample_rate = sample_rate
        # Max listen window (seconds). Ends earlier on sustained silence.
        self.record_seconds = record_seconds

        # Voice activity settings.
        self.silence_threshold = silence_threshold
        # How long silence must last before we stop (avoids cutting mid-thought)
        self.silence_duration = silence_duration
        self.minimum_record_seconds = minimum_record_seconds

        self.whisper_model = None

        self.tts_engine = pyttsx3.init()
        self._configure_natural_voice()

        # Optional neural TTS (edge-tts). Falls back to pyttsx3.
        self.tts_backend = "pyttsx3"  # or "edge"
        self.edge_voice = "en-US-JennyNeural"
        self._try_enable_edge_tts()

        self._tts_lock = threading.Lock()
        self._stop_requested = threading.Event()

        # Event used to stop microphone recording.
        self._record_stop_requested = threading.Event()

    # --------------------------------------------------
    # NATURAL VOICE SETUP
    # --------------------------------------------------

    def _configure_natural_voice(self):
        """
        Pick the most natural Windows SAPI voice available
        and use a slightly slower, clearer rate.
        """
        try:
            voices = self.tts_engine.getProperty("voices") or []
            preferred_keywords = [
                "jenny", "aria", "guy", "sara", "zira",
                "david", "mark", "hazel", "susan", "neural",
                "natural", "english",
            ]

            chosen = None
            for keyword in preferred_keywords:
                for voice in voices:
                    name = (getattr(voice, "name", "") or "").lower()
                    vid = (getattr(voice, "id", "") or "").lower()
                    if keyword in name or keyword in vid:
                        chosen = voice.id
                        break
                if chosen:
                    break

            if chosen:
                self.tts_engine.setProperty("voice", chosen)

            # Slightly slower = more natural pacing
            self.tts_engine.setProperty("rate", 165)
            self.tts_engine.setProperty("volume", 1.0)
        except Exception:
            try:
                self.tts_engine.setProperty("rate", 165)
                self.tts_engine.setProperty("volume", 1.0)
            except Exception:
                pass

    def _try_enable_edge_tts(self):
        """
        Prefer Microsoft Edge neural voices when edge-tts is installed.
        These sound far more human than classic SAPI voices.
        """
        try:
            import edge_tts  # noqa: F401
            self.tts_backend = "edge"
        except Exception:
            self.tts_backend = "pyttsx3"

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """
        Strip markdown and tool-noise so speech sounds conversational.
        """
        import re

        text = str(text)
        # Remove fenced code blocks
        text = re.sub(r"```[\s\S]*?```", " ", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Bold / italic markers
        text = re.sub(r"[*_#]+", " ", text)
        # Bullet markers
        text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _split_sentences(text: str):
        """Split into short speakable chunks."""
        import re

        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    # --------------------------------------------------
    # WHISPER
    # --------------------------------------------------

    def load_whisper(self):
        """
        Load Whisper only when voice is actually used.
        """

        if self.whisper_model is None:

            self.whisper_model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )

    def transcribe(self, audio):
        """
        Convert microphone audio into text.
        """

        if audio is None:
            return ""

        if len(audio) == 0:
            return ""

        self.load_whisper()

        segments, info = self.whisper_model.transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=True,
        )

        text = "".join(
            segment.text for segment in segments
        ).strip()

        return text

    # --------------------------------------------------
    # MICROPHONE RECORDING
    # --------------------------------------------------

    def record_audio(self):
        """
        Record microphone input.

        Recording ends when:

        - The maximum recording duration is reached.
        - stop_listening() is called.
        - Speech is detected and then followed by
          a short period of silence.
        """

        self._record_stop_requested.clear()

        recorded_chunks = []

        speech_detected = False
        silence_start = None

        print("Listening...")

        def audio_callback(
            indata,
            frames,
            time_info,
            status,
        ):
            nonlocal speech_detected
            nonlocal silence_start

            if status:
                print(
                    f"Microphone status: {status}"
                )

            chunk = indata.copy()

            recorded_chunks.append(chunk)

            # Calculate the RMS volume of this
            # microphone chunk.
            volume = float(
                np.sqrt(
                    np.mean(
                        np.square(chunk)
                    )
                )
            )

            current_time = time.monotonic()

            # ------------------------------------------
            # SPEECH DETECTED
            # ------------------------------------------

            if volume >= self.silence_threshold:

                speech_detected = True
                silence_start = None

            # ------------------------------------------
            # SILENCE AFTER SPEECH
            # ------------------------------------------

            elif speech_detected:

                if silence_start is None:

                    silence_start = current_time

                elif (
                    current_time - silence_start
                    >= self.silence_duration
                ):

                    self._record_stop_requested.set()

        try:

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                callback=audio_callback,
            ):

                start_time = time.monotonic()

                while not self._record_stop_requested.is_set():

                    elapsed = (
                        time.monotonic()
                        - start_time
                    )

                    # Never record longer than the
                    # configured maximum.
                    if elapsed >= self.record_seconds:

                        break

                    self._record_stop_requested.wait(
                        0.05
                    )

        except Exception:

            print(
                "Microphone recording failed."
            )

            raise

        print("Recording finished.")

        if not recorded_chunks:

            return np.array(
                [],
                dtype=np.float32,
            )

        audio = np.concatenate(
            recorded_chunks,
            axis=0,
        )

        audio = audio.squeeze()

        # Prevent extremely short recordings from
        # being sent unnecessarily to Whisper.
        if len(audio) == 0:

            return np.array(
                [],
                dtype=np.float32,
            )

        duration = (
            len(audio)
            / self.sample_rate
        )

        if duration < self.minimum_record_seconds:

            return np.array(
                [],
                dtype=np.float32,
            )

        return audio

    def stop_listening(self):
        """
        Request that the active microphone recording stop.
        """

        self._record_stop_requested.set()

    def listen(self):
        """
        Record and transcribe one voice command.
        """

        audio = self.record_audio()

        if audio.size == 0:

            return ""

        return self.transcribe(audio)

    def listen_for_wake(self, phrase: str = "aethra") -> bool:
        """Short listen used by the wake-word loop. Does not start the app."""
        previous = self.record_seconds
        self.record_seconds = 4
        try:
            heard = (self.listen() or "").lower()
        finally:
            self.record_seconds = previous
        return phrase.lower() in heard

    # --------------------------------------------------
    # TEXT TO SPEECH
    # --------------------------------------------------

    def speak(self, text):
        """
        Speak text in a more natural, conversational way.

        - Cleans markdown / code for speech
        - Speaks sentence by sentence with short pauses
        - Uses Edge neural voices when available, else improved SAPI
        """

        if not text:
            return

        text = self._clean_for_speech(text)
        if not text:
            return

        with self._tts_lock:
            self._stop_requested.clear()

            try:
                if self.tts_backend == "edge":
                    self._speak_edge(text)
                else:
                    self._speak_pyttsx3(text)
            finally:
                try:
                    self.tts_engine.stop()
                except Exception:
                    pass

    def _speak_pyttsx3(self, text: str):
        """Speak the full reply in one pass so it is not cut after the first line."""
        if self._stop_requested.is_set():
            return
        self.tts_engine.say(text[:1200])
        self.tts_engine.runAndWait()

    def _speak_edge(self, text: str):
        """
        Neural TTS via edge-tts (Microsoft voices).
        Requires: pip install edge-tts pygame
        Needs network when synthesizing speech.
        Falls back to improved SAPI if anything fails.
        """
        import asyncio
        import os
        import tempfile

        try:
            import edge_tts
        except ImportError:
            self.tts_backend = "pyttsx3"
            self._speak_pyttsx3(text)
            return

        sentences = self._split_sentences(text)
        if not sentences:
            sentences = [text]

        async def _synth(sentence: str, path: str):
            communicate = edge_tts.Communicate(
                sentence,
                self.edge_voice,
            )
            await communicate.save(path)

        # Lazy init pygame mixer once
        mixer_ready = False
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            mixer_ready = True
        except Exception:
            mixer_ready = False

        if not mixer_ready:
            self.tts_backend = "pyttsx3"
            self._speak_pyttsx3(text)
            return

        import pygame

        for sentence in sentences:
            if self._stop_requested.is_set():
                break

            tmp = None
            try:
                fd, tmp = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)

                asyncio.run(_synth(sentence, tmp))

                if self._stop_requested.is_set():
                    break

                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_requested.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)

                if not self._stop_requested.is_set():
                    time.sleep(0.15)

            except Exception:
                # Fall back for remaining text
                self.tts_backend = "pyttsx3"
                self._speak_pyttsx3(sentence)
            finally:
                if tmp and os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

    def stop_speaking(self):
        """
        Request that the current speech be stopped.
        """

        self._stop_requested.set()

        try:
            self.tts_engine.stop()
        except Exception as exc:
            print(f"Could not stop speech cleanly: {exc}")


# ======================================================
# VOICE WORKER
# ======================================================

class VoiceWorker(QThread):
    """
    Runs microphone recording and transcription outside
    the main Qt UI thread.
    """

    finished = Signal(str)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, voice_engine):

        super().__init__()

        self.voice_engine = voice_engine

    def run(self):

        try:

            self.status.emit(
                "Listening..."
            )

            audio = (
                self.voice_engine.record_audio()
            )

            # ------------------------------------------
            # NO SPEECH
            # ------------------------------------------

            if audio.size == 0:

                self.status.emit(
                    "No speech detected."
                )

                self.finished.emit("")

                return

            # ------------------------------------------
            # TRANSCRIPTION
            # ------------------------------------------

            self.status.emit(
                "Transcribing..."
            )

            text = (
                self.voice_engine.transcribe(
                    audio
                )
            )

            if not text:

                self.status.emit(
                    "I didn't catch that."
                )

            self.finished.emit(text)

        except Exception as exc:

            self.error.emit(
                str(exc)
            )