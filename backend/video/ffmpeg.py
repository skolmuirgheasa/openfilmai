from pathlib import Path
import subprocess
from typing import Tuple

# Default timeout for ffmpeg/ffprobe operations (seconds)
FFMPEG_TIMEOUT = 60
FFPROBE_TIMEOUT = 15


def extract_first_last_frames(video_path: str, out_first: str, out_last: str) -> Tuple[str, str]:
    """
    Extract first and last frames from a video file.

    Handles edge cases:
    - Very short videos (< 1 second)
    - Corrupted videos (timeout protection)
    - Missing duration metadata
    """
    video = Path(video_path)
    first = Path(out_first)
    last = Path(out_last)

    if not video.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Ensure output directories exist
    first.parent.mkdir(parents=True, exist_ok=True)
    last.parent.mkdir(parents=True, exist_ok=True)

    # First frame - use simple seeking to start
    try:
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(video), "-ss", "0", "-vframes", "1", str(first)
        ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
        if result.returncode != 0:
            print(f"Error extracting first frame: {result.stderr}")
        else:
            print(f"First frame extracted successfully: {first}")
    except subprocess.TimeoutExpired:
        print(f"Timeout extracting first frame from {video_path}")
    except Exception as e:
        print(f"Exception extracting first frame: {e}")

    # Last frame - use duration-based seeking with robustness
    duration = get_video_duration(str(video))

    if duration > 0.5:
        # Normal case: video has known duration > 0.5s
        # Seek to 0.1s before end for reliability
        seek_time = max(0, duration - 0.1)
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-ss", str(seek_time), "-i", str(video), "-vframes", "1", str(last)
            ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode != 0:
                print(f"Error extracting last frame: {result.stderr}")
            else:
                print(f"Last frame extracted successfully: {last}")
        except subprocess.TimeoutExpired:
            print(f"Timeout extracting last frame from {video_path}")
        except Exception as e:
            print(f"Exception extracting last frame: {e}")
    elif duration > 0:
        # Very short video (< 0.5s): use the only frame we can get
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-i", str(video), "-vframes", "1", str(last)
            ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode != 0:
                print(f"Error extracting last frame (short video): {result.stderr}")
            else:
                print(f"Last frame extracted from short video: {last}")
        except subprocess.TimeoutExpired:
            print(f"Timeout extracting last frame from short video {video_path}")
        except Exception as e:
            print(f"Exception extracting last frame (short video): {e}")
    else:
        # Duration probe failed - use sseof fallback
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-sseof", "-0.5", "-i", str(video), "-vframes", "1", str(last)
            ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode != 0:
                # Final fallback: just grab first frame as last
                print(f"sseof fallback failed, using first frame as last: {result.stderr}")
                result = subprocess.run([
                    "ffmpeg", "-y", "-i", str(video), "-vframes", "1", str(last)
                ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"Timeout extracting last frame (fallback) from {video_path}")
        except Exception as e:
            print(f"Exception extracting last frame (fallback): {e}")

    return str(first), str(last)


def extract_frame_at_timestamp(video_path: str, timestamp_seconds: float, output_path: str) -> str:
    """
    Extract a single frame from a video at a specific timestamp.

    Args:
        video_path: Path to the video file
        timestamp_seconds: Time in seconds (can be decimal like 2.5)
        output_path: Path where frame will be saved (should end in .png or .jpg)

    Returns:
        Path to the extracted frame

    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If extraction fails
    """
    video = Path(video_path)
    output = Path(output_path)

    if not video.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    # Clamp timestamp to valid range
    duration = get_video_duration(str(video))
    if duration > 0:
        timestamp_seconds = max(0, min(timestamp_seconds, duration - 0.05))
    else:
        timestamp_seconds = max(0, timestamp_seconds)

    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(timestamp_seconds),
            "-i", str(video),
            "-vframes", "1",
            "-q:v", "2",  # High quality
            str(output)
        ], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error extracting frame: {result.stderr}")

        if not output.exists():
            raise RuntimeError(f"Frame extraction failed - output not created")

        print(f"[FFMPEG] Extracted frame at {timestamp_seconds}s -> {output}")
        return str(output)

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout extracting frame at {timestamp_seconds}s from {video_path}")


def get_video_duration(video_path: str) -> float:
    """
    Get the duration of a video file in seconds.

    Includes timeout protection for corrupted files.
    Returns 0.0 if duration cannot be determined.
    """
    video = Path(video_path)

    if not video.exists():
        print(f"Warning: Video file not found: {video_path}")
        return 0.0

    # Try format duration first
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video)
        ], capture_output=True, text=True, timeout=FFPROBE_TIMEOUT)

        if probe.returncode == 0 and probe.stdout.strip():
            try:
                val = float(probe.stdout.strip())
                if val > 0:
                    return val
            except ValueError:
                pass
    except subprocess.TimeoutExpired:
        print(f"Timeout probing duration (format) for {video_path}")
    except Exception as e:
        print(f"Error probing duration (format): {e}")

    # Fallback to stream duration if format duration fails
    try:
        probe_stream = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video)
        ], capture_output=True, text=True, timeout=FFPROBE_TIMEOUT)

        if probe_stream.returncode == 0 and probe_stream.stdout.strip():
            try:
                val = float(probe_stream.stdout.strip())
                if val > 0:
                    return val
            except ValueError:
                pass
    except subprocess.TimeoutExpired:
        print(f"Timeout probing duration (stream) for {video_path}")
    except Exception as e:
        print(f"Error probing duration (stream): {e}")

    print(f"Warning: Could not determine duration for {video_path}")
    return 0.0


def replace_first_frame(video_path: str, replacement_frame: str, output_path: str) -> str:
    """
    Replace the first frame of a video with a specific image.
    This ensures perfect continuity when the replacement frame is from the previous clip.
    
    Args:
        video_path: Path to video whose first frame will be replaced
        replacement_frame: Path to image that will become the new first frame
        output_path: Path where modified video will be saved
    
    Returns:
        Path to the modified video
    """
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        # Extract all frames except the first one
        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        
        # Get frame rate
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ], capture_output=True, text=True)
        
        if probe.returncode != 0:
            raise RuntimeError(f"Failed to probe frame rate: {probe.stderr}")
        
        fps_str = probe.stdout.strip()
        # Parse fraction (e.g., "24/1" -> 24)
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str)
        
        # Extract frames starting from frame 2 (skip first frame)
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", "select='gte(n\\,1)'",  # Skip first frame (n=0)
            "-vsync", "0",
            str(frames_dir / "frame_%04d.png")
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to extract frames: {result.stderr}")
        
        # Copy replacement frame as frame_0000.png
        import shutil
        shutil.copy2(replacement_frame, frames_dir / "frame_0000.png")
        
        # Reassemble video from frames
        result = subprocess.run([
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%04d.png"),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            str(output_path)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to reassemble video: {result.stderr}")
        
        if not Path(output_path).exists():
            raise RuntimeError("Output file was not created")
    
    return output_path


def optical_flow_smooth(input_a: str, input_b: str, output_path: str, transition_frames: int = 0) -> str:
    """
    ACTUALLY CORRECT clip stitching - just skip B's duplicate first frame.
    
    THE PROBLEM:
    - When B is generated from A's last frame, B's first frame is ALREADY identical to A's last
    - This creates a duplicate frame at the join point
    
    THE SOLUTION:
    - Simply skip B's first frame (which is the duplicate)
    - Concatenate A + trimmed B
    - DON'T replace B's first frame - that would re-add the duplicate!
    
    Result: Seamless, no duplicate frames, no stutter.
    
    Args:
        input_a: Path to first video clip
        input_b: Path to second video clip
        output_path: Path where merged video will be saved
        transition_frames: Unused (kept for API compatibility)
    
    Returns:
        Path to the merged video file
    
    Raises:
        RuntimeError: If FFmpeg commands fail
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        # Step 1: Skip B's first frame (the duplicate of A's last frame)
        # Use select filter to skip frame 0, keep frames 1+
        # Also trim audio by 1 frame duration (1/24 = ~0.042s) to maintain sync
        trimmed_b = tmp / "trimmed_b.mp4"
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(input_b),
            "-vf", "select='gte(n\\,1)',setpts=PTS-STARTPTS",
            "-af", "atrim=start=0.042,asetpts=PTS-STARTPTS",  # Trim audio by 1 frame (1/24s)
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "128k",
            str(trimmed_b)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not trimmed_b.exists():
            raise RuntimeError(f"Failed to trim B: {result.stderr}")
        
        # Step 2: Get resolution from A
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(input_a)
        ], capture_output=True, text=True)
        
        if probe.returncode != 0 or not probe.stdout.strip():
            raise RuntimeError(f"Failed to probe video A: {probe.stderr}")
        
        width, height = probe.stdout.strip().split(',')
        
        # Step 3: Normalize both clips to same resolution and format
        normalized_a = tmp / "normalized_a.mp4"
        normalized_b = tmp / "normalized_b.mp4"
        
        # Normalize A
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(input_a),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "128k",  # Keep audio!
            str(normalized_a)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not normalized_a.exists():
            raise RuntimeError(f"Failed to normalize video A: {result.stderr}")
        
        # Normalize trimmed B
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(trimmed_b),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "128k",  # Keep audio!
            str(normalized_b)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not normalized_b.exists():
            raise RuntimeError(f"Failed to normalize video B: {result.stderr}")
        
        # Step 4: Concatenate using filter_complex for perfect A/V sync
        # Check if both clips have audio streams
        probe_a_audio = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0", str(normalized_a)
        ], capture_output=True, text=True)
        
        probe_b_audio = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0", str(normalized_b)
        ], capture_output=True, text=True)
        
        has_audio_a = probe_a_audio.returncode == 0 and "audio" in probe_a_audio.stdout
        has_audio_b = probe_b_audio.returncode == 0 and "audio" in probe_b_audio.stdout
        
        # Build filter_complex based on audio availability
        if has_audio_a and has_audio_b:
            # Both have audio - concat both video and audio
            filter_complex = "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]"
            map_args = ["-map", "[outv]", "-map", "[outa]"]
            audio_codec = ["-c:a", "aac", "-b:a", "128k"]
        elif has_audio_a or has_audio_b:
            # Only one has audio - concat video, copy single audio
            filter_complex = "[0:v][1:v]concat=n=2:v=1[outv]"
            if has_audio_a:
                map_args = ["-map", "[outv]", "-map", "0:a"]
            else:
                map_args = ["-map", "[outv]", "-map", "1:a"]
            audio_codec = ["-c:a", "aac", "-b:a", "128k"]
        else:
            # Neither has audio - video only
            filter_complex = "[0:v][1:v]concat=n=2:v=1[outv]"
            map_args = ["-map", "[outv]"]
            audio_codec = []
        
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(normalized_a),
            "-i", str(normalized_b),
            "-filter_complex", filter_complex,
            *map_args,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            *audio_codec,
            str(output_path)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")
        
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


def pad_audio_to_duration(input_audio: str, target_duration: float, output_audio: str) -> str:
    """
    Pad an audio file with silence to match a target duration.
    This ensures WaveSpeed generates video matching the original video length.
    
    Args:
        input_audio: Path to input audio file
        target_duration: Target duration in seconds
        output_audio: Path where padded audio will be saved
    
    Returns:
        Path to the padded audio file
    """
    # Get current audio duration
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(input_audio)
    ], capture_output=True, text=True)
    
    if probe.returncode != 0:
        raise RuntimeError(f"Failed to probe audio duration: {probe.stderr}")
    
    current_duration = float(probe.stdout.strip())
    
    # If audio is already long enough, just copy it
    if current_duration >= target_duration - 0.1:  # 0.1s tolerance
        import shutil
        shutil.copy2(input_audio, output_audio)
        return output_audio
    
    # Pad with silence to match target duration
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_audio),
        "-af", f"apad=whole_dur={target_duration}",
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_audio)
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to pad audio: {result.stderr}")
    
    if not Path(output_audio).exists():
        raise RuntimeError("Padded audio file was not created")
    
    return output_audio


def ensure_compatible_format(input_video: str, output_video: str) -> str:
    """
    Re-encode video to ensure browser compatibility.
    Uses H.264 codec with yuv420p pixel format for maximum compatibility.
    """
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",  # Enable streaming
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_video)
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg format conversion failed: {result.stderr}")
    
    if not Path(output_video).exists():
        raise RuntimeError("Output file was not created")
    
    return output_video


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


def extend_lipsync_video(lipsync_video: str, original_video: str, output_path: str) -> str:
    """
    Extend a lip-synced video to match the original video's duration.
    WaveSpeed truncates videos to audio length, so we append the remaining original footage.
    
    Args:
        lipsync_video: Path to the lip-synced video (truncated to audio length)
        original_video: Path to the original full-length video
        output_path: Path where extended video will be saved
    
    Returns:
        Path to the extended video
    """
    import tempfile
    
    # Get durations
    probe_lipsync = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(lipsync_video)
    ], capture_output=True, text=True)
    
    probe_original = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(original_video)
    ], capture_output=True, text=True)
    
    if probe_lipsync.returncode != 0 or probe_original.returncode != 0:
        raise RuntimeError("Failed to probe video durations")
    
    lipsync_duration = float(probe_lipsync.stdout.strip())
    original_duration = float(probe_original.stdout.strip())
    
    # If lip-sync is already same length or longer, just copy it
    if lipsync_duration >= original_duration - 0.1:  # 0.1s tolerance
        import shutil
        shutil.copy2(lipsync_video, output_path)
        return output_path
    
    # Extract the remaining part of the original video
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        remaining_part = tmp / "remaining.mp4"
        
        # Cut from lipsync_duration to end of original
        result = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(lipsync_duration),
            "-i", str(original_video),
            "-c", "copy",
            str(remaining_part)
        ], capture_output=True, text=True)
        
        if result.returncode != 0 or not remaining_part.exists():
            raise RuntimeError(f"Failed to extract remaining video: {result.stderr}")
        
        # Concatenate lip-synced part + remaining part
        concat_file = tmp / "concat.txt"
        with open(concat_file, "w") as f:
            f.write(f"file '{Path(lipsync_video).absolute()}'\n")
            f.write(f"file '{remaining_part.absolute()}'\n")
        
        result = subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to concatenate videos: {result.stderr}")
        
        if not Path(output_path).exists():
            raise RuntimeError("Output file was not created")
    
    return output_path


