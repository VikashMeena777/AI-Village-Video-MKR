"""
compose_scenes.py - FFmpeg Scene Composer & Merger

Composes audio onto video for each scene, then merges all scenes
into final reel format (9:16, 30-45 seconds).
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Directories
VIDEOS_DIR = Path("outputs/videos")
AUDIO_DIR = Path("outputs/audio")
COMPOSED_DIR = Path("outputs/composed")
FINAL_DIR = Path("outputs/final")

COMPOSED_DIR.mkdir(parents=True, exist_ok=True)
FINAL_DIR.mkdir(parents=True, exist_ok=True)


def get_media_duration(file_path: str) -> float:
    """Get duration of media file using ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ], capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 5.0  # Default duration


def compose_scene(scene_id: int, video_path: str, audio_files: list) -> str:
    """
    Compose a single scene: overlay all dialogue audio onto video.
    Audio files are placed sequentially with small gaps.
    """
    output_path = COMPOSED_DIR / f"scene_{scene_id}_composed.mp4"
    
    if not Path(video_path).exists():
        print(f"  Warning: Video not found: {video_path}")
        return None
    
    # If no audio, just copy video
    if not audio_files:
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-c:v", "copy", "-an",
            str(output_path)
        ], capture_output=True)
        return str(output_path)
    
    # Calculate audio placement timing
    video_duration = get_media_duration(video_path)
    num_dialogues = len(audio_files)
    gap = 0.3  # Gap between dialogues
    
    # Build complex filter for audio mixing
    filter_parts = []
    audio_inputs = ["-i", video_path]
    
    current_time = 0.2  # Start slightly after beginning
    
    for idx, audio_info in enumerate(audio_files):
        audio_path = audio_info.get("path", "")
        if not Path(audio_path).exists():
            continue
        
        audio_inputs.extend(["-i", audio_path])
        audio_idx = idx + 1  # 0 is video
        
        # Delay this audio to start at current_time
        filter_parts.append(f"[{audio_idx}:a]adelay={int(current_time*1000)}|{int(current_time*1000)}[a{idx}]")
        
        # Update timing for next dialogue
        audio_duration = get_media_duration(audio_path)
        current_time += audio_duration + gap
    
    if not filter_parts:
        # No valid audio files, copy video
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-c:v", "copy", "-an",
            str(output_path)
        ], capture_output=True)
        return str(output_path)
    
    # Mix all audio tracks
    audio_labels = "".join([f"[a{i}]" for i in range(len(filter_parts))])
    filter_parts.append(f"{audio_labels}amix=inputs={len(filter_parts)}:duration=longest[aout]")
    
    filter_complex = ";".join(filter_parts)
    
    # Run FFmpeg
    cmd = [
        "ffmpeg", "-y",
        *audio_inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path)
    ]
    
    print(f"  Composing scene {scene_id}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[:200]}")
        # Fallback: just copy video without audio
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-c:v", "copy", "-an",
            str(output_path)
        ], capture_output=True)
    
    return str(output_path)


def merge_scenes(composed_videos: list) -> str:
    """
    Merge all composed scenes into final reel.
    Output: 9:16 aspect ratio, 30-45 seconds target.
    """
    output_path = FINAL_DIR / "final_reel.mp4"
    
    # Filter out None values
    valid_videos = [v for v in composed_videos if v and Path(v).exists()]
    
    if not valid_videos:
        print("Error: No valid composed videos to merge")
        return None
    
    # Create concat file
    concat_file = FINAL_DIR / "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video in valid_videos:
            f.write(f"file '{Path(video).absolute()}'\n")
    
    # Merge with format conversion to 9:16
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    print("\nMerging all scenes into final reel...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Merge error: {result.stderr[:500]}")
        return None
    
    # Get final duration
    duration = get_media_duration(str(output_path))
    print(f"Final reel created: {output_path}")
    print(f"Duration: {duration:.1f} seconds")
    
    return str(output_path)


def main():
    """Main entry point."""
    
    print("=" * 50)
    print("Scene Composer & Merger (FFmpeg)")
    print("=" * 50)
    
    # Load video paths
    video_paths_file = Path("outputs/video_paths.json")
    if video_paths_file.exists():
        video_paths = json.loads(video_paths_file.read_text())
    else:
        # Fallback: find videos in directory
        video_paths = sorted([str(p) for p in VIDEOS_DIR.glob("scene_*.mp4")])
    
    # Load audio data
    audio_paths_file = Path("outputs/audio_paths.json")
    if audio_paths_file.exists():
        audio_data = json.loads(audio_paths_file.read_text())
    else:
        audio_data = []
    
    # Create audio lookup by scene_id
    audio_by_scene = {s["scene_id"]: s["audio_files"] for s in audio_data}
    
    print(f"\nFound {len(video_paths)} videos, {len(audio_data)} audio scene sets")
    
    # Compose each scene
    composed_videos = []
    for idx, video_path in enumerate(video_paths):
        scene_id = idx + 1
        audio_files = audio_by_scene.get(scene_id, [])
        
        print(f"\nScene {scene_id}: {len(audio_files)} audio files")
        composed = compose_scene(scene_id, video_path, audio_files)
        composed_videos.append(composed)
    
    # Merge all scenes
    final_reel = merge_scenes(composed_videos)
    
    if final_reel:
        # Save final path
        Path("outputs/final_reel_path.txt").write_text(final_reel)
        print(f"\n✅ Success! Final reel: {final_reel}")
    else:
        print("\n❌ Failed to create final reel")
        sys.exit(1)


if __name__ == "__main__":
    main()
