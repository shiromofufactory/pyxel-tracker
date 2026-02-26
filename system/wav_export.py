import os
import wave

import pyxel

try:
    import pyaudio
except Exception:
    pyaudio = None


TICKS_PER_SECOND = 120
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHUNK = 1024
START_DETECT_MIN_ABS = 64
START_DETECT_CONSECUTIVE = 8
MAX_START_WAIT_SEC = 2.0
TAIL_GUARD_SEC = 0.5
PRE_ROLL_SEC = 0.1

LOOPBACK_KEYWORDS = (
    "blackhole",
    "loopback",
    "soundflower",
    "stereo mix",
    "monitor",
)


def _normalize_sound(sound):
    if sound is None:
        return None
    if isinstance(sound, dict):
        speed = sound.get("speed", 1)
        return [
            sound.get("notes", ""),
            sound.get("tones", ""),
            sound.get("volumes", ""),
            sound.get("effects", ""),
            speed,
        ]
    if isinstance(sound, list):
        if len(sound) == 4:
            return [sound[0], sound[1], sound[2], sound[3], 1]
        if len(sound) >= 5:
            return [sound[0], sound[1], sound[2], sound[3], sound[4]]
    raise ValueError("Unsupported sound format")


def _count_note_steps(notes):
    if notes is None:
        return 0
    if isinstance(notes, (list, tuple)):
        return len(notes)
    if not isinstance(notes, str):
        return 0
    count = 0
    idx = 0
    while idx < len(notes):
        c = notes[idx].lower()
        if c in (" ", ",", "\t", "\n"):
            idx += 1
            continue
        if c == "r":
            count += 1
            idx += 1
            continue
        if c in ("c", "d", "e", "f", "g", "a", "b"):
            idx += 1
            if idx < len(notes) and notes[idx] == "#":
                idx += 1
            while idx < len(notes) and notes[idx].isdigit():
                idx += 1
            count += 1
            continue
        # Unknown char: skip it without counting a note.
        idx += 1
    return count


def calc_total_ticks(compiled_music):
    max_ticks = 0
    for sound in compiled_music:
        normalized = _normalize_sound(sound)
        if normalized is None:
            continue
        note_steps = _count_note_steps(normalized[0])
        speed = normalized[4] if normalized[4] else 1
        ticks = note_steps * speed
        if ticks > max_ticks:
            max_ticks = ticks
    return max_ticks


def calc_total_seconds(compiled_music):
    return calc_total_ticks(compiled_music) / TICKS_PER_SECOND


def _choose_input_device(audio):
    env_index = os.getenv("PYXEL_TRACKER_WAV_INPUT_DEVICE_INDEX")
    if env_index:
        return int(env_index)

    env_name = os.getenv("PYXEL_TRACKER_WAV_INPUT_DEVICE_NAME")
    if env_name:
        key = env_name.lower()
        for idx in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(idx)
            if info.get("maxInputChannels", 0) <= 0:
                continue
            if key in info.get("name", "").lower():
                return idx
        raise RuntimeError(
            "No input device matched PYXEL_TRACKER_WAV_INPUT_DEVICE_NAME."
        )

    for idx in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(idx)
        if info.get("maxInputChannels", 0) <= 0:
            continue
        name = info.get("name", "").lower()
        if any(keyword in name for keyword in LOOPBACK_KEYWORDS):
            return idx

    return audio.get_default_input_device_info()["index"]


def _detect_start_frame(samples, channels, sample_rate, noise_frames):
    if not samples:
        return None
    total_frames = len(samples) // channels
    noise_window = min(total_frames, max(1, noise_frames))
    noise_peak = 0
    for frame_idx in range(noise_window):
        base = frame_idx * channels
        level = 0
        for ch in range(channels):
            ch_level = abs(samples[base + ch])
            if ch_level > level:
                level = ch_level
        if level > noise_peak:
            noise_peak = level
    # Estimate threshold from pre-roll noise only.
    threshold = max(START_DETECT_MIN_ABS, noise_peak * 2 + 32)
    consecutive = 0
    for frame_idx in range(total_frames):
        base = frame_idx * channels
        level = 0
        for ch in range(channels):
            ch_level = abs(samples[base + ch])
            if ch_level > level:
                level = ch_level
        if level >= threshold:
            consecutive += 1
            if consecutive >= START_DETECT_CONSECUTIVE:
                return frame_idx - START_DETECT_CONSECUTIVE + 1
        else:
            consecutive = 0
    return None


def export_compiled_music_to_wav(compiled_music, out_path):
    if pyaudio is None:
        raise RuntimeError(
            "PyAudio is not installed. Install it to use WAV export recording."
        )
    duration_sec = calc_total_seconds(compiled_music)
    if duration_sec <= 0:
        raise RuntimeError("Music duration is zero.")

    for ch in range(4):
        sound = _normalize_sound(compiled_music[ch] if ch < len(compiled_music) else None)
        if sound is None:
            continue
        pyxel.sounds[ch].set(*sound)

    audio = pyaudio.PyAudio()
    stream = None
    sample_rate = DEFAULT_SAMPLE_RATE
    channels = 1
    try:
        device_index = _choose_input_device(audio)
        info = audio.get_device_info_by_index(device_index)
        sample_rate = int(info.get("defaultSampleRate", DEFAULT_SAMPLE_RATE))
        max_input_channels = int(info.get("maxInputChannels", 1))
        channels = 1 if max_input_channels >= 1 else max_input_channels
        if channels <= 0:
            raise RuntimeError("Selected input device does not support input channels.")

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=DEFAULT_CHUNK,
                input_device_index=device_index,
            )
        except Exception:
            if max_input_channels >= 2:
                channels = 2
                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    frames_per_buffer=DEFAULT_CHUNK,
                    input_device_index=device_index,
                )
            else:
                raise

        capture_sec = PRE_ROLL_SEC + duration_sec + MAX_START_WAIT_SEC + TAIL_GUARD_SEC
        total_frames = int(capture_sec * sample_rate)
        total_chunks = (total_frames + DEFAULT_CHUNK - 1) // DEFAULT_CHUNK
        pre_roll_frames = int(PRE_ROLL_SEC * sample_rate)
        pre_roll_chunks = (pre_roll_frames + DEFAULT_CHUNK - 1) // DEFAULT_CHUNK

        pyxel.stop()

        recorded = []
        for _ in range(pre_roll_chunks):
            chunk = stream.read(DEFAULT_CHUNK, exception_on_overflow=False)
            recorded.append(chunk)

        for ch in range(4):
            if ch < len(compiled_music) and _normalize_sound(compiled_music[ch]) is not None:
                pyxel.play(ch, [ch])

        for _ in range(total_chunks - pre_roll_chunks):
            chunk = stream.read(DEFAULT_CHUNK, exception_on_overflow=False)
            recorded.append(chunk)

        raw = b"".join(recorded)
        samples = memoryview(raw).cast("h")
        start_frame = _detect_start_frame(
            samples, channels, sample_rate, pre_roll_frames
        )
        if start_frame is None:
            raise RuntimeError(
                "Failed to detect playback start in recorded input. "
                "Set a loopback input device (e.g. BlackHole) and retry."
            )
        start = start_frame * channels
        take_frames = int(duration_sec * sample_rate)
        end = start + take_frames * channels
        if end > len(samples):
            raise RuntimeError("Recorded data is shorter than calculated duration.")
        clipped = samples[start:end].tobytes()

        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with wave.open(out_path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(clipped)
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        audio.terminate()
