"""Speaker diarization — identify speakers in audio recordings."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def diarize_audio(file_path: str) -> list[dict]:
    """Identify speakers in an audio file.

    Returns list of segments: [{speaker, start, end}]
    Falls back to single-speaker if pyannote not available.
    """
    try:
        from pyannote.audio import Pipeline
        import torch

        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=True,
        )

        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))

        diarization = pipeline(file_path)

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 2),
                "end": round(turn.end, 2),
            })

        # Renumber speakers to friendly names
        speaker_map = {}
        counter = 1
        for seg in segments:
            if seg["speaker"] not in speaker_map:
                speaker_map[seg["speaker"]] = f"Speaker {counter}"
                counter += 1
            seg["speaker"] = speaker_map[seg["speaker"]]

        return segments

    except ImportError:
        logger.warning("pyannote.audio not installed; returning single-speaker fallback")
        return [{"speaker": "Speaker 1", "start": 0.0, "end": 0.0}]
    except Exception as e:
        logger.error("Diarization failed: %s", e)
        return [{"speaker": "Speaker 1", "start": 0.0, "end": 0.0}]


def merge_transcript_and_diarization(
    transcript_segments: list[dict],
    diarization_segments: list[dict],
) -> list[dict]:
    """Merge transcript with speaker labels.

    transcript_segments: [{text, start, end}]
    diarization_segments: [{speaker, start, end}]

    Returns: [{speaker, text, start, end}]
    """
    if not diarization_segments or not transcript_segments:
        return [
            {**seg, "speaker": "Speaker 1"}
            for seg in transcript_segments
        ]

    result = []
    for tseg in transcript_segments:
        t_mid = (tseg.get("start", 0) + tseg.get("end", 0)) / 2
        best_speaker = "Unknown"
        best_overlap = 0

        for dseg in diarization_segments:
            overlap_start = max(tseg.get("start", 0), dseg["start"])
            overlap_end = min(tseg.get("end", 0), dseg["end"])
            overlap = max(0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = dseg["speaker"]

        result.append({
            "speaker": best_speaker,
            "text": tseg.get("text", ""),
            "start": tseg.get("start", 0),
            "end": tseg.get("end", 0),
        })

    return result
