"""
Vocal separation bằng Demucs (Meta AI, mã nguồn mở, giấy phép MIT).
Không dùng API trả phí — model chạy hoàn toàn local bằng PyTorch.

Demucs v4 (htdemucs) tách 1 bài thành 4 stem: vocals, drums, bass, other.
- vocal.wav        = stem "vocals"
- instrumental.wav = tổng (drums + bass + other)
- bass.wav / drums.wav / other.wav = xuất thêm vì model hỗ trợ 4-stem

Lần đầu chạy với 1 model_tag mới, Demucs tự tải trọng số (qua torch.hub) về
$TORCH_HOME/hub/checkpoints — đã được cấu hình trỏ vào models/torch_cache
trong backend/config.py để tận dụng Railway Volume nếu có.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import torch
import torchaudio

from backend.core.logger import get_logger

logger = get_logger("separation")

_MODEL_CACHE: dict[str, "object"] = {}


def _load_model(model_tag: str):
    """Load (và cache trong process) 1 model Demucs theo tag, ví dụ 'htdemucs'."""
    if model_tag in _MODEL_CACHE:
        return _MODEL_CACHE[model_tag]

    from demucs.pretrained import get_model

    logger.info(f"Đang load Demucs model '{model_tag}' (tải về nếu chưa có trong cache)...")
    model = get_model(name=model_tag)
    model.eval()
    _MODEL_CACHE[model_tag] = model
    logger.info(f"Model '{model_tag}' sẵn sàng. Các stem: {model.sources}")
    return model


def ensure_model_downloaded(model_tag: str) -> list[str]:
    """Dùng bởi Model Manager khi admin bấm 'install': ép tải weights về ngay,
    trả về danh sách tên các stem mà model này hỗ trợ."""
    model = _load_model(model_tag)
    return list(model.sources)


def separate_audio(
    input_path: str,
    model_tag: str,
    output_dir: str,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> dict[str, str]:
    """
    Chạy tách nguồn âm thanh thật bằng Demucs.
    Trả về dict {stem_name: file_path}, luôn có 'vocal' và 'instrumental',
    kèm thêm 'bass'/'drums'/'other' nếu model hỗ trợ 4-stem.
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile, save_audio
    from backend.config import settings

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb(10)
    model = _load_model(model_tag)

    if progress_cb:
        progress_cb(25)

    max_seconds = settings.max_separation_seconds
    wav = AudioFile(input_path).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    max_frames = int(max_seconds * model.samplerate) if max_seconds else None
    if max_frames and wav.shape[-1] > max_frames:
        logger.warning(
            f"File dài hơn {max_seconds}s — chỉ tách {max_seconds}s đầu để tránh OOM."
        )
        wav = wav[..., :max_frames]

    ref = wav.mean(0)
    wav_norm = (wav - ref.mean()) / (ref.std() + 1e-8)

    if progress_cb:
        progress_cb(35)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    with torch.no_grad():
        sources = apply_model(
            model, wav_norm[None], device=device, progress=False, split=True
        )[0]
    sources = sources * ref.std() + ref.mean()

    if progress_cb:
        progress_cb(80)

    stem_paths: dict[str, str] = {}
    instrumental = None
    for source_wave, source_name in zip(sources, model.sources):
        dest = out_dir / f"{source_name}.wav"
        save_audio(source_wave, str(dest), samplerate=model.samplerate)
        stem_paths[source_name] = str(dest)
        if source_name != "vocals":
            instrumental = source_wave if instrumental is None else instrumental + source_wave

    # Chuẩn hóa tên theo yêu cầu: vocal.wav / instrumental.wav (+ bass/drums/other nếu có)
    result: dict[str, str] = {}
    if "vocals" in stem_paths:
        vocal_dest = out_dir / "vocal.wav"
        Path(stem_paths["vocals"]).rename(vocal_dest)
        result["vocal"] = str(vocal_dest)

    if instrumental is not None:
        instrumental_dest = out_dir / "instrumental.wav"
        save_audio(instrumental, str(instrumental_dest), samplerate=model.samplerate)
        result["instrumental"] = str(instrumental_dest)

    for stem in ("bass", "drums", "other"):
        if stem in stem_paths:
            result[stem] = stem_paths[stem]

    if progress_cb:
        progress_cb(100)

    logger.info(f"Tách vocal hoàn tất cho {input_path}: {list(result.keys())}")
    return result
