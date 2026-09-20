"""Command-line interface for the Multimedia Tool pipeline."""

import os
import json
import argparse
import logging
from src.director.planner import DirectorPlanner
from src.seedance.client import SeedanceClient
from src.qa.audit import VideoQAAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("multimedia_tool")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Retro Pixel & Seedance Video Generator")
    parser.add_argument("--topic", type=str, required=True, help="Main topic or title to explain")
    parser.add_argument("--context", type=str, default=None, help="Raw domain text or technical background context")
    parser.add_argument("--context-file", type=str, default=None, help="Path to markdown/text file containing detailed context")
    parser.add_argument("--character-name", type=str, default="Hermes", help="Name of persistent character")
    parser.add_argument("--character-image", type=str, default=None, help="Path or URL to character reference image")
    parser.add_argument("--character-prompt", type=str, default=None, help="Visual description tokens of the character")
    parser.add_argument("--chapters", type=int, default=4, help="Number of roadmap chapters (default: 4)")
    parser.add_argument("--output-dir", type=str, default="./renders", help="Output directory for generated files")
    parser.add_argument("--skip-video-gen", action="store_true", help="Only generate storyboard JSON without calling Seedance")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    cutscenes_dir = os.path.join(args.output_dir, "cutscenes")
    os.makedirs(cutscenes_dir, exist_ok=True)

    # 1. Assemble Global Context
    context_text = args.context or ""
    if args.context_file and os.path.exists(args.context_file):
        with open(args.context_file, "r", encoding="utf-8") as f:
            context_text += "\n" + f.read()

    global_context = {
        "domain_notes": context_text.strip(),
        "tone": "educational, 16-bit retro gaming, cinematic",
        "target_audience": "technical professionals and learners"
    } if context_text.strip() else None

    # 2. Assemble Character Profile
    char_profile = {
        "name": args.character_name,
        "reference_image_url": args.character_image or "assets/characters/hermes_reference.png",
        "prompt_tokens": args.character_prompt or "chibi hero with golden winged helmet, blue messenger tunic, and golden caduceus",
        "sprite_id": "hermes_pixel"
    }

    # 3. Director Planning
    logger.info(f"--- 1. Planning Storyboard for topic: '{args.topic}' ---")
    planner = DirectorPlanner()
    storyboard = planner.plan_storyboard(
        topic_or_transcript=args.topic,
        global_context=global_context,
        character_profile=char_profile,
        chapter_count=args.chapters
    )
    
    storyboard_path = os.path.join(args.output_dir, "storyboard.json")
    with open(storyboard_path, "w") as f:
        json.dump(storyboard, f, indent=2)
    logger.info(f"Storyboard saved to {storyboard_path}")

    if args.skip_video_gen:
        logger.info("Skipping Seedance video generation as requested (--skip-video-gen).")
        return

    # 4. Seedance Video Generation (Watermark-Free with Multimodal Reference)
    logger.info("--- 2. Generating Watermark-Free Cutscenes via Seedance with Character Consistency ---")
    seedance = SeedanceClient()
    qa = VideoQAAgent()

    ref_image = char_profile["reference_image_url"] if (char_profile["reference_image_url"] and os.path.exists(char_profile["reference_image_url"])) else None

    for ch in storyboard.get("chapters", []):
        ch_id = ch["id"]
        prompt = ch["seedance_prompt"]
        clip_path = os.path.join(cutscenes_dir, f"chapter_{ch_id}.mp4")
        
        logger.info(f"Generating Cutscene for Chapter {ch_id}: '{ch['title']}'...")
        seedance.generate_video(
            prompt=prompt,
            output_path=clip_path,
            character_reference_image=ref_image,
            watermark=False,  # Enforce no watermark
            duration=int(ch.get("duration_seconds", 5))
        )

        # 5. QA Audit
        passed, reason = qa.audit_clip(clip_path)
        if not passed:
            logger.warning(f"Chapter {ch_id} failed QA: {reason}")
        else:
            logger.info(f"Chapter {ch_id} clip passed QA audit.")

    logger.info("--- Pipeline Completed Successfully! ---")
    logger.info(f"All assets ready in {args.output_dir}. Ready for Remotion compilation.")

if __name__ == "__main__":
    main()
