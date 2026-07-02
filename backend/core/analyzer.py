"""
Music Analyzer: phân tích BPM, key, mode, tuning, và nhận diện hợp âm theo timeline.
Toàn bộ xử lý bằng librosa/numpy thật — không giả lập kết quả.

Kỹ thuật:
- Tempo: librosa.beat.beat_track (onset envelope + dynamic programming)
- Key/Mode: chroma trung bình toàn bài so khớp với Krumhansl-Schmuckler key profiles
- Chord theo timeline: chia bài thành các khung (frame) ~ theo beat, tính chroma mỗi khung,
  so khớp với template nhị phân của từng loại hợp âm (major, minor, 7, maj7, sus2, sus4, dim, aug, ...)
  bằng cosine similarity, chọn hợp âm khớp nhất mỗi khung, rồi gộp các khung liên tiếp trùng hợp âm.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, asdict

import librosa
import numpy as np

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Schmuckler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Định nghĩa các loại hợp âm bằng khoảng cách nửa cung tính từ nốt gốc (root = 0)
CHORD_TEMPLATES: dict[str, list[int]] = {
    "":    [0, 4, 7],          # major
    "m":   [0, 3, 7],          # minor
    "aug": [0, 4, 8],
    "dim": [0, 3, 6],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "6":   [0, 4, 7, 9],
    "m6":  [0, 3, 7, 9],
    "7":   [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7":  [0, 3, 7, 10],
    "dim7": [0, 3, 6, 9],
    "m7b5": [0, 3, 6, 10],
    "add9": [0, 4, 7, 2],
    "maj9": [0, 4, 7, 11, 2],
    "m9":  [0, 3, 7, 10, 2],
}


def _chord_template_vector(root: int, intervals: list[int]) -> np.ndarray:
    vec = np.zeros(12)
    for iv in intervals:
        vec[(root + iv) % 12] = 1.0
    return vec


# Build toàn bộ 12 x số loại hợp âm template vector 1 lần (không hardcode lặp lại trong loop nóng)
_ALL_CHORD_VECTORS: list[tuple[str, np.ndarray]] = []
for root in range(12):
    for suffix, intervals in CHORD_TEMPLATES.items():
        label = f"{NOTE_NAMES[root]}{suffix}"
        _ALL_CHORD_VECTORS.append((label, _chord_template_vector(root, intervals)))


@dataclass
class ChordEvent:
    time: float
    chord: str

    def to_dict(self):
        return asdict(self)


@dataclass
class AnalysisResult:
    bpm: float
    tempo_confidence: float
    key: str
    mode: str
    sample_rate: int
    duration: float
    tuning: float
    chords: list[ChordEvent]

    def to_dict(self):
        d = asdict(self)
        d["chords"] = [c.to_dict() if isinstance(c, ChordEvent) else c for c in self.chords]
        return d


def _estimate_key(chroma_mean: np.ndarray) -> tuple[str, str]:
    best_score = -np.inf
    best_key, best_mode = "C", "major"
    for shift in range(12):
        maj = np.roll(MAJOR_PROFILE, shift)
        minr = np.roll(MINOR_PROFILE, shift)
        maj_score = np.corrcoef(chroma_mean, maj)[0, 1]
        min_score = np.corrcoef(chroma_mean, minr)[0, 1]
        if maj_score > best_score:
            best_score, best_key, best_mode = maj_score, NOTE_NAMES[shift], "major"
        if min_score > best_score:
            best_score, best_key, best_mode = min_score, NOTE_NAMES[shift], "minor"
    return best_key, best_mode


def _match_chord(chroma_frame: np.ndarray) -> str:
    best_label, best_score = "N", -np.inf
    norm = np.linalg.norm(chroma_frame)
    if norm < 1e-6:
        return "N"  # No chord / im lặng
    chroma_norm = chroma_frame / norm
    for label, template in _ALL_CHORD_VECTORS:
        t_norm = template / np.linalg.norm(template)
        score = float(np.dot(chroma_norm, t_norm))
        if score > best_score:
            best_score, best_label = score, label
    return best_label


def analyze_audio(file_path: str) -> AnalysisResult:
    import soundfile as sf
    from backend.config import settings

    # Lấy metadata (sample rate gốc, duration thật) mà KHÔNG load toàn bộ audio vào RAM.
    info = sf.info(file_path)
    native_sr = info.samplerate
    full_duration = info.frames / float(native_sr)

    max_seconds = settings.max_analysis_seconds
    load_duration = min(full_duration, max_seconds) if max_seconds else full_duration
    truncated = full_duration > load_duration

    # Downsample về analysis_sample_rate (mặc định 22050) để giảm ~1 nửa RAM/CPU so với
    # sr gốc (thường 44100/48000) — không ảnh hưởng đáng kể tới chroma/tempo/key detection.
    analysis_sr = settings.analysis_sample_rate
    y, sr = librosa.load(
        file_path, sr=analysis_sr, mono=True, duration=load_duration
    )

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    ac = librosa.autocorrelate(onset_env, max_size=len(onset_env))
    tempo_confidence = float(np.clip(ac.max() / (np.sum(np.abs(ac)) + 1e-9) * 10, 0, 1))

    tuning = float(librosa.estimate_tuning(y=y, sr=sr))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, tuning=tuning)
    chroma_mean = chroma.mean(axis=1)
    key, mode = _estimate_key(chroma_mean)

    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    if len(beat_times) < 2:
        beat_times = np.arange(0, load_duration, 2.0)

    chroma_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)

    chords: list[ChordEvent] = []
    last_chord = None
    for bt in beat_times:
        idx = int(np.argmin(np.abs(chroma_times - bt)))
        frame = chroma[:, idx]
        chord_label = _match_chord(frame)
        if chord_label != last_chord:
            chords.append(ChordEvent(time=round(float(bt), 2), chord=chord_label))
            last_chord = chord_label

    if truncated:
        chords.append(ChordEvent(
            time=round(load_duration, 2),
            chord=f"[Đã dừng phân tích ở {int(load_duration)}s để tránh quá tải RAM]",
        ))

    # Giải phóng mảng audio lớn ngay khi không cần nữa
    del y, chroma

    return AnalysisResult(
        bpm=round(float(tempo), 2),
        tempo_confidence=round(tempo_confidence, 3),
        key=key,
        mode=mode,
        sample_rate=int(native_sr),
        duration=round(float(full_duration), 2),
        tuning=round(tuning, 4),
        chords=chords,
    )


def format_timeline_txt(result: AnalysisResult) -> str:
    lines = [f"BPM: {result.bpm} | Key: {result.key} {result.mode} | Duration: {result.duration}s", ""]
    for c in result.chords:
        m, s = divmod(int(c.time), 60)
        lines.append(f"{m:02d}:{s:02d} {c.chord}")
    return "\n".join(lines)
