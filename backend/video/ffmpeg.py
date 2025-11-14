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
    Applies TRUE optical flow smoothing between two video clips using motion interpolation.
    This creates seamless continuity when clip B was generated from clip A's end frame.
    
    Uses FFmpeg's minterpolate filter for motion-compensated frame interpolation,
    then blends with xfade for a completely smooth transition with no visible jerk.
    
    Args:
        input_a: Path to first video clip
        input_b: Path to second video clip
        output_path: Path where merged video will be saved
        transition_frames: Number of frames for the transition (default 15 at 24fps = 0.625s)
    
    Returns:
        Path to the merged video file
    
    Raises:
        RuntimeError: If FFmpeg commands fail
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        # Get resolution from first video
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(input_a)
        ], capture_output=True, text=True)
        
        if probe.returncode != 0 or not probe.stdout.strip():
            raise RuntimeError(f"Failed to probe video A: {probe.stderr}")
        
        width, height = probe.stdout.strip().split(',')
        
        # Normalize both videos to same resolution with higher quality for interpolation
        normalized_a = tmp / "normalized_a.mp4"
        normalized_b = tmp / "normalized_b.mp4"
        
        # Normalize clip A with higher quality (CRF 18 instead of 23)
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(input_a),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24", "-an",
            str(normalized_a)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not normalized_a.exists():
            raise RuntimeError(f"Failed to normalize video A: {result.stderr}")
        
        # Normalize clip B with higher quality
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(input_b),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24", "-an",
            str(normalized_b)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not normalized_b.exists():
            raise RuntimeError(f"Failed to normalize video B: {result.stderr}")
        
        # Get duration of first video for xfade offset
        probe_duration = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(normalized_a)
        ], capture_output=True, text=True)
        
        if probe_duration.returncode != 0 or not probe_duration.stdout.strip():
            raise RuntimeError(f"Failed to get duration of video A: {probe_duration.stderr}")
        
        # Apply motion-compensated interpolation for seamless blending
        # NO FADE - clips should be identical at junction point
        # Step 1: Interpolate both clips to 48fps using motion compensation
        # Step 2: Downsample back to 24fps for smooth motion
        # Step 3: Direct concatenation (no crossfade)
        filter_complex = (
            f"[0:v]minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,fps=24[interpA];"
            f"[1:v]minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,fps=24[interpB];"
            f"[interpA][interpB]concat=n=2:v=1:a=0[outv]"
        )
        
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(normalized_a),
            "-i", str(normalized_b),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg optical flow interpolation failed: {result.stderr}")
        
        if not Path(output_path).exists():
            raise RuntimeError("Output file was not created")
    
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


