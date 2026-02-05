"""
generate_tts.py - Hindi Text-to-Speech Generator

Uses Edge TTS (Microsoft) - completely free, no API key needed.
Generates Hindi audio for all dialogues.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Edge TTS is the best free option for Hindi
import edge_tts

# Output directory
OUTPUT_DIR = Path("outputs/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Voice mapping for characters
VOICE_MAP = {
    "maa": "hi-IN-SwaraNeural",      # Female, warm
    "behen": "hi-IN-SwaraNeural",     # Female, young
    "baap": "hi-IN-MadhurNeural",     # Male, deep
    "hero": "hi-IN-MadhurNeural",     # Male, intense
    "dost": "hi-IN-MadhurNeural",     # Male, casual
    "gav_wale": "hi-IN-MadhurNeural", # Male, neutral
}

# Voice adjustments for character personality
VOICE_SETTINGS = {
    "maa": {"rate": "-5%", "pitch": "+5Hz"},
    "behen": {"rate": "+0%", "pitch": "+10Hz"},
    "baap": {"rate": "-10%", "pitch": "-10Hz"},
    "hero": {"rate": "-15%", "pitch": "-20Hz"},  # Slow, deep for rage
    "dost": {"rate": "+5%", "pitch": "+0Hz"},
    "gav_wale": {"rate": "+0%", "pitch": "+0Hz"},
}


async def generate_audio(text: str, character: str, output_path: str) -> str:
    """
    Generate Hindi TTS audio using Edge TTS.
    """
    voice = VOICE_MAP.get(character, "hi-IN-MadhurNeural")
    settings = VOICE_SETTINGS.get(character, {})
    
    rate = settings.get("rate", "+0%")
    pitch = settings.get("pitch", "+0Hz")
    
    print(f"  Generating: {character} -> {voice} (rate={rate}, pitch={pitch})")
    
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch
    )
    
    await communicate.save(output_path)
    return output_path


async def process_script(script: dict) -> list:
    """
    Process all dialogues in the script and generate audio files.
    Returns list of audio file paths organized by scene.
    """
    scenes = script.get("scenes", [])
    all_audio_paths = []
    
    for scene in scenes:
        scene_id = scene.get("scene_id", len(all_audio_paths) + 1)
        dialogues = scene.get("dialogues", [])
        
        scene_audio = []
        print(f"\nScene {scene_id}: {len(dialogues)} dialogues")
        
        for idx, dialogue in enumerate(dialogues):
            character = dialogue.get("character", "narrator")
            text = dialogue.get("text", "")
            
            if not text:
                continue
            
            output_path = OUTPUT_DIR / f"scene{scene_id}_{character}_{idx+1}.mp3"
            
            try:
                await generate_audio(text, character, str(output_path))
                scene_audio.append({
                    "path": str(output_path),
                    "character": character,
                    "text": text,
                    "scene_id": scene_id,
                    "order": idx + 1
                })
            except Exception as e:
                print(f"  Error generating audio: {e}")
        
        all_audio_paths.append({
            "scene_id": scene_id,
            "audio_files": scene_audio
        })
    
    return all_audio_paths


def main():
    """Main entry point."""
    
    # Get script from environment or file
    script_json = os.environ.get("SCRIPT_JSON")
    if not script_json:
        script_file = Path("outputs/script.json")
        if script_file.exists():
            script_json = script_file.read_text()
        else:
            print("Error: No script found. Set SCRIPT_JSON env or create outputs/script.json")
            sys.exit(1)
    
    script = json.loads(script_json)
    
    print("=" * 50)
    print("Hindi TTS Generator (Edge TTS)")
    print("=" * 50)
    
    # Run async processing
    audio_data = asyncio.run(process_script(script))
    
    # Save audio paths for next step
    audio_file = Path("outputs/audio_paths.json")
    audio_file.write_text(json.dumps(audio_data, indent=2, ensure_ascii=False))
    print(f"\nSaved audio data to {audio_file}")
    
    # Summary
    total_files = sum(len(s["audio_files"]) for s in audio_data)
    print(f"\nGenerated {total_files} audio files across {len(audio_data)} scenes")


if __name__ == "__main__":
    main()
