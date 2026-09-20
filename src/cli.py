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
    parser.add_argument("--topic", type=str, required=True, help="Topic or transcript to transform into a video")
    parser.add_argument("--chapters", type=int, default=4, help="Number of roadmap chapters (default: 4)")
    parser.add_argument("--output-dir", type=str, default="./renders", help="Output directory for generated files")
    parser.add_argument("--skip-video-gen", action="store_true", help="Only generate storyboard JSON without calling Seedance")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    cutscenes_dir = os.path.join(args.output_dir, "cutscenes")
    os.makedirs(cutscenes_dir, exist_ok=True)

    # 1. Director Planning
    logger.info(f"--- 1. Planning Storyboard for topic: '{args.topic}' ---")
    planner = DirectorPlanner()
    storyboard = planner.plan_storyboard(args.topic, chapter_count=args.chapters)
    
    storyboard_path = os.path.join(args.output_dir, "storyboard.json")
    with open(storyboard_path, "w") as f:
        json.dump(storyboard, f, indent=2)
    logger.info(f"Storyboard saved to {storyboard_path}")

    if args.skip_video_gen:
        logger.info("Skipping Seedance video generation as requested (--skip-video-gen).")
        return

    # 2. Seedance Video Generation (Watermark-Free)
    logger.info("--- 2. Generating Watermark-Free Cutscenes via Seedance ---")
    seedance = SeedanceClient()
    qa = VideoQAAgent()

    for ch in storyboard.get("chapters", []):
        ch_id = ch["id"]
        prompt = ch["seedance_prompt"]
        clip_path = os.path.join(cutscenes_dir, f"chapter_{ch_id}.mp4")
        
        logger.info(f"Generating Cutscene for Chapter {ch_id}: '{ch['title']}'...")
        seedance.generate_video(
            prompt=prompt,
            output_path=clip_path,
            watermark=False,  # Enforce no watermark
            duration=int(ch.get("duration_seconds", 5))
        )

        # 3. QA Audit
        passed, reason = qa.audit_clip(clip_path)
        if not passed:
            logger.warning(f"Chapter {ch_id} failed QA: {reason}")
        else:
            logger.info(f"Chapter {ch_id} clip passed QA audit.")

    logger.info("--- Pipeline Completed Successfully! ---")
    logger.info(f"All assets ready in {args.output_dir}. Ready for Remotion compilation.")

if __name__ == "__main__":
    main()
