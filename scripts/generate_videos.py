"""
generate_videos.py - HuggingFace Space Video Generator

Uses free HuggingFace Spaces for text-to-video generation.
Supports: LTX-Video, CogVideoX, ModelScopeT2V
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# Available HuggingFace Spaces for text-to-video (free)
VIDEO_SPACES = {
    "ltx": "Lightricks/LTX-Video",
    "cogvideo": "THUDM/CogVideoX-5b",
    "modelscope": "damo-vilab/modelscope-text-to-video-synthesis",
}

# Default space to use
DEFAULT_SPACE = "ltx"

# Output directory
OUTPUT_DIR = Path("outputs/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_video_prompt(scene: dict) -> str:
    """
    Build video generation prompt from scene data.
    NO Marvel references - uses generic muscular giant.
    """
    emotion = scene.get("emotion", "neutral")
    location = scene.get("location", "village_chowk")
    
    # Location descriptions
    locations = {
        "village_chowk": "village central square with old banyan tree",
        "ghar_aangan": "rustic home courtyard with mud walls",
        "khet": "golden wheat fields at sunset",
        "handpump_area": "village handpump with women gathering water",
        "panchayat_ground": "open ground with elders sitting",
    }
    
    # Emotion to visual mapping
    emotions = {
        "conflict": "tense confrontation, angry gestures",
        "sadness": "tearful, emotional embrace",
        "anger_building": "clenched fists, visible frustration",
        "rage": "explosive anger, dramatic transformation, muscles bulging",
        "shock": "stunned expressions, stepping back in fear",
    }
    
    base_prompt = f"""
Rural Indian village scene.
{locations.get(location, 'dusty village road')}.
Mud houses, handpump, dusty paths, neem trees in background.
A tall green-skinned muscular man with rippling muscles and torn farmer clothing.
{emotions.get(emotion, 'neutral expression')}.
Cinematic camera angle, dramatic lighting.
No text, no watermark, no subtitles.
Duration: 5-6 seconds.
    """.strip()
    
    return base_prompt


def generate_video_gradio(prompt: str, scene_id: int, space_id: str = DEFAULT_SPACE) -> str:
    """
    Generate video using Gradio Client for HuggingFace Space.
    Returns path to downloaded video.
    """
    try:
        from gradio_client import Client
        
        space_name = VIDEO_SPACES.get(space_id, VIDEO_SPACES[DEFAULT_SPACE])
        print(f"[Scene {scene_id}] Connecting to {space_name}...")
        
        client = Client(space_name)
        
        # Submit generation request
        print(f"[Scene {scene_id}] Generating video...")
        result = client.predict(
            prompt=prompt,
            api_name="/generate"  # May vary by space
        )
        
        # Download/save result
        output_path = OUTPUT_DIR / f"scene_{scene_id}.mp4"
        
        if isinstance(result, str) and os.path.exists(result):
            import shutil
            shutil.copy(result, output_path)
        else:
            # Result might be a URL
            print(f"[Scene {scene_id}] Downloading from URL...")
            response = requests.get(result, stream=True)
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"[Scene {scene_id}] Saved to {output_path}")
        return str(output_path)
        
    except Exception as e:
        print(f"[Scene {scene_id}] Error: {e}")
        raise


def generate_video_api(prompt: str, scene_id: int) -> str:
    """
    Alternative: Direct API call to HuggingFace Inference API.
    Requires HF_TOKEN environment variable.
    """
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("HF_TOKEN environment variable required")
    
    api_url = "https://api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
    headers = {"Authorization": f"Bearer {hf_token}"}
    
    print(f"[Scene {scene_id}] Calling HF Inference API...")
    
    response = requests.post(api_url, headers=headers, json={"inputs": prompt})
    
    if response.status_code == 200:
        output_path = OUTPUT_DIR / f"scene_{scene_id}.mp4"
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"[Scene {scene_id}] Saved to {output_path}")
        return str(output_path)
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")


def main():
    """Main entry point - reads script JSON from environment or file."""
    
    # Get script from environment (passed by n8n) or file
    script_json = os.environ.get("SCRIPT_JSON")
    if not script_json:
        script_file = Path("outputs/script.json")
        if script_file.exists():
            script_json = script_file.read_text()
        else:
            print("Error: No script found. Set SCRIPT_JSON env or create outputs/script.json")
            sys.exit(1)
    
    script = json.loads(script_json)
    scenes = script.get("scenes", [])
    
    print(f"Processing {len(scenes)} scenes...")
    
    video_paths = []
    for scene in scenes:
        scene_id = scene.get("scene_id", len(video_paths) + 1)
        prompt = build_video_prompt(scene)
        
        print(f"\n{'='*50}")
        print(f"Scene {scene_id} Prompt:\n{prompt}")
        print(f"{'='*50}\n")
        
        try:
            # Try Gradio client first
            video_path = generate_video_gradio(prompt, scene_id)
        except Exception as e:
            print(f"Gradio failed, trying API: {e}")
            try:
                video_path = generate_video_api(prompt, scene_id)
            except Exception as e2:
                print(f"API also failed: {e2}")
                # Create placeholder for testing
                video_path = str(OUTPUT_DIR / f"scene_{scene_id}_placeholder.mp4")
                Path(video_path).touch()
        
        video_paths.append(video_path)
        
        # Rate limiting - wait between requests
        time.sleep(2)
    
    # Save paths for next step
    paths_file = Path("outputs/video_paths.json")
    paths_file.write_text(json.dumps(video_paths, indent=2))
    print(f"\nSaved video paths to {paths_file}")


if __name__ == "__main__":
    main()
