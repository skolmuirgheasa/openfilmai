from pathlib import Path
import subprocess
from typing import Tuple


def extract_first_last_frames(video_path: str, out_first: str, out_last: str) -> Tuple[str, str]:
    video = Path(video_path)
    first = Path(out_first)
    last = Path(out_last)

    # First frame
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video), "-vf", "select=eq(n\\,0)", "-vframes", "1", str(first)
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Last frame
    subprocess.run([
        "ffmpeg", "-y", "-sseof", "-1", "-i", str(video), "-vframes", "1", str(last)
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return str(first), str(last)


def optical_flow_smooth(input_a: str, input_b: str, output_path: str) -> str:
    # Simple placeholder for optical-flow-based smoothing
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_a),
        "-i", str(input_b),
        "-lavfi", "mpdecimate;minterpolate=fps=60:mi_mode=mci",
        str(output_path)
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


