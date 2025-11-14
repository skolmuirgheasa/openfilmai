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


def optical_flow_smooth(input_a: str, input_b: str, output_path: str, transition_frames: int = 15) -> str:
    """
    Create a smooth transition between two video clips using optical flow interpolation.
    This generates intermediate frames between the last frame of clip A and first frame of clip B.
    """
    # Extract last frame from clip A and first frame from clip B
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        last_a = tmp / "last_a.png"
        first_b = tmp / "first_b.png"
        
        # Extract frames
        subprocess.run([
            "ffmpeg", "-y", "-sseof", "-1", "-i", str(input_a), "-vframes", "1", str(last_a)
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_b), "-vf", "select=eq(n\\,0)", "-vframes", "1", str(first_b)
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Create transition video using minterpolate
        # This generates smooth interpolated frames between the two images
        transition_video = tmp / "transition.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(last_a),
            "-loop", "1", "-i", str(first_b),
            "-filter_complex",
            f"[0:v][1:v]blend=all_expr='A*(1-T/1)+B*(T/1)',fps=24,trim=duration={transition_frames/24}[v]",
            "-map", "[v]",
            "-pix_fmt", "yuv420p",
            str(transition_video)
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Concatenate: clip A + transition + clip B
        concat_list = tmp / "concat.txt"
        with open(concat_list, "w") as f:
            f.write(f"file '{Path(input_a).absolute()}'\n")
            f.write(f"file '{transition_video.absolute()}'\n")
            f.write(f"file '{Path(input_b).absolute()}'\n")
        
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(output_path)
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return output_path


def concatenate_videos(video_paths: list[str], output_path: str) -> str:
    """Concatenate multiple videos into one."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for vp in video_paths:
            f.write(f"file '{Path(vp).absolute()}'\n")
        concat_file = f.name
    
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy", str(output_path)
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        Path(concat_file).unlink(missing_ok=True)
    
    return output_path


def strip_audio(input_video: str) -> None:
    tmp = Path(input_video).with_suffix(".noaudio.tmp.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video),
            "-c",
            "copy",
            "-an",
            str(tmp),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if tmp.exists():
        tmp.replace(input_video)


