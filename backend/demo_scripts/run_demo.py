"""Replay a fictional script through the live API for a stage demo.

Example:
    cd backend && python demo_scripts/run_demo.py --script critical_en
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import textwrap
import wave
from pathlib import Path
from typing import Any

import httpx
import websockets

SCRIPT_NAMES = (
    "benign_en",
    "benign_hi",
    "medium_en",
    "medium_hi",
    "critical_en",
    "critical_hi",
)
SCRIPT_DIRECTORY = Path(__file__).resolve().parent


def load_script(script_name: str) -> str:
    """Read a checked-in fictional script and remove its comment header."""

    if script_name not in SCRIPT_NAMES:
        raise ValueError(f"Unknown script {script_name!r}; choose from {', '.join(SCRIPT_NAMES)}")
    path = SCRIPT_DIRECTORY / f"{script_name}.txt"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    return " ".join(line.strip() for line in lines if line.strip())


def split_into_chunks(script_text: str, characters_per_chunk: int = 180) -> list[str]:
    """Approximate two-second speech chunks using word boundaries."""

    words = script_text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        proposed_length = current_length + len(word) + (1 if current else 0)
        if current and proposed_length > characters_per_chunk:
            chunks.append(" ".join(current))
            current = []
            current_length = 0
        current.append(word)
        current_length += len(word) + (1 if current_length else 0)
    if current:
        chunks.append(" ".join(current))
    return chunks


def make_demo_wav(text: str, duration_seconds: float = 2.0) -> bytes:
    """Create silent PCM with an in-band marker for offline transcription.

    The marker is only used when Groq is unavailable in a local demo. A real
    deployment sends the WAV bytes to Whisper and never persists this buffer.
    """

    sample_rate = 16_000
    frame_count = int(sample_rate * duration_seconds)
    pcm_silence = b"\x00\x00" * frame_count
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_silence)
    return buffer.getvalue() + b"\nDEMO_TEXT:" + text.encode("utf-8")


def print_payload(index: int, payload: dict[str, Any]) -> None:
    """Print one compact risk result in a terminal-friendly table."""

    reasons = "; ".join(str(reason) for reason in payload.get("reasons", [])[:2]) or "No strong indicators"
    print(
        f"{index:>3} | score {float(payload.get('final_score', 0)):>6.2f} | "
        f"{str(payload.get('verdict', 'UNKNOWN')):<10} | "
        f"script {float(payload.get('script_score', 0)):>5.1f} | {reasons}"
    )


def print_final(payload: dict[str, Any]) -> None:
    """Render a large final verdict banner."""

    verdict = str(payload.get("verdict", "UNKNOWN"))
    score = float(payload.get("final_score", 0.0))
    border = "=" * 62
    print(f"\n{border}\n              FINAL VERDICT: {verdict}\n              RISK SCORE: {score:.1f}/100\n{border}\n")


async def run(script_name: str, base_url: str) -> None:
    """Send every fictional chunk and print the returned RiskPayloads."""

    script_text = load_script(script_name)
    chunks = split_into_chunks(script_text)
    normalized_base = base_url.rstrip("/")
    start_url = f"{normalized_base}/session/start"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(start_url, json={"language": "auto", "is_practice": True})
        response.raise_for_status()
        session_id = str(response.json()["session_id"])

    websocket_base = normalized_base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    websocket_url = f"{websocket_base}/ws/call/{session_id}"
    print(f"Armour demo: {script_name} ({len(chunks)} two-second chunks)")
    print(" #  |        SCORE | VERDICT    | SCRIPT | REASONS")
    print("-" * 110)
    final_payload: dict[str, Any] = {}
    async with websockets.connect(websocket_url, max_size=2**20) as socket:
        for index, chunk in enumerate(chunks, start=1):
            # A rolling text marker keeps the offline demo equivalent to the
            # sliding transcript context used by the live intent pipeline.
            rolling_chunk = " ".join(chunks[:index])
            await socket.send(make_demo_wav(rolling_chunk))
            raw_payload = await socket.recv()
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            import json

            final_payload = json.loads(raw_payload)
            print_payload(index, final_payload)
    print_final(final_payload)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Replay an Armour fictional scam script")
    parser.add_argument("--script", required=True, choices=SCRIPT_NAMES)
    parser.add_argument(
        "--base-url",
        default=os.getenv("VITE_BACKEND_HTTP_URL", "http://localhost:8000"),
        help="Backend HTTP base URL",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""

    args = parse_args()
    try:
        asyncio.run(run(args.script, args.base_url))
    except (httpx.HTTPError, OSError, websockets.WebSocketException) as exc:
        raise SystemExit(f"Demo could not connect to the backend: {exc}") from exc


if __name__ == "__main__":
    main()
