import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, Video } from "remotion";
import { ParallaxBackground } from "../components/ParallaxBackground";
import { PlatformNode } from "../components/PlatformNode";
import { HermesAvatar } from "../components/HermesAvatar";

export interface Chapter {
  id: number;
  title: string;
  narration_text: string;
  platform: { x: number; y: number; width?: number };
  seedance_prompt: string;
  cutscene_mode?: string;
  duration_seconds: number;
  cutscene_video_url?: string;
}

export interface MasterRoadmapVideoProps {
  storyboard: {
    theme?: string;
    chapters: Chapter[];
  };
}

export const MasterRoadmapVideo: React.FC<MasterRoadmapVideoProps> = ({ storyboard }) => {
  const frame = useCurrentFrame();
  const fps = 60;
  const chapters = storyboard.chapters || [];

  if (chapters.length === 0) {
    return <AbsoluteFill style={{ backgroundColor: "#060919" }} />;
  }

  // Calculate timing boundaries:
  // Each chapter gets: JUMP_TIME (e.g. 1.2s = 72 frames) + DWELL_TIME (duration_seconds * fps)
  const JUMP_FRAMES = 72;
  const chapterTimings: { startFrame: number; jumpEndFrame: number; endFrame: number }[] = [];

  let currentFrameCursor = 0;
  for (let i = 0; i < chapters.length; i++) {
    const dwellFrames = Math.round(chapters[i].duration_seconds * fps);
    const startFrame = currentFrameCursor;
    const jumpEndFrame = startFrame + JUMP_FRAMES;
    const endFrame = jumpEndFrame + dwellFrames;
    chapterTimings.push({ startFrame, jumpEndFrame, endFrame });
    currentFrameCursor = endFrame;
  }

  // Determine current active chapter
  let activeIndex = 0;
  for (let i = 0; i < chapterTimings.length; i++) {
    if (frame >= chapterTimings[i].startFrame && frame < chapterTimings[i].endFrame) {
      activeIndex = i;
      break;
    }
    if (i === chapterTimings.length - 1 && frame >= chapterTimings[i].endFrame) {
      activeIndex = i;
    }
  }

  const timing = chapterTimings[activeIndex];
  const prevChapter = activeIndex > 0 ? chapters[activeIndex - 1] : null;
  const currentChapter = chapters[activeIndex];

  // Character coordinates
  let charX = currentChapter.platform.x;
  let charY = currentChapter.platform.y - 36; // sit directly on top of platform
  let isJumping = false;
  let facingRight = true;

  if (frame < timing.jumpEndFrame && prevChapter) {
    // We are currently in jump transition from prevChapter -> currentChapter
    isJumping = true;
    const jumpProgress = interpolate(
      frame,
      [timing.startFrame, timing.jumpEndFrame],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    const startX = prevChapter.platform.x;
    const endX = currentChapter.platform.x;
    const startY = prevChapter.platform.y - 36;
    const endY = currentChapter.platform.y - 36;

    facingRight = endX >= startX;
    charX = interpolate(jumpProgress, [0, 1], [startX, endX]);

    // Parabolic arc: 4 * max_height * p * (1 - p)
    const arcHeight = 120;
    const jumpOffset = 4 * arcHeight * jumpProgress * (1 - jumpProgress);
    charY = interpolate(jumpProgress, [0, 1], [startY, endY]) - jumpOffset;
  }

  // Camera tracking (smooth center follow on character X)
  const cameraX = charX - 1920 / 2;

  // Cutscene overlay (if video exists and we are in dwell phase)
  const hasCutscene = Boolean(currentChapter.cutscene_video_url);
  const isCutsceneActive = hasCutscene && frame >= timing.jumpEndFrame + 30; // 0.5s pause before cutscene
  const cutsceneOpacity = isCutsceneActive
    ? interpolate(frame, [timing.jumpEndFrame + 30, timing.jumpEndFrame + 60], [0, 1], {
        extrapolateRight: "clamp",
      })
    : 0;

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#060919" }}>
      {/* 1. Parallax World Background */}
      <ParallaxBackground cameraX={cameraX} />

      {/* 2. World Camera Container */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          transform: `translateX(${-cameraX}px)`,
        }}
      >
        {/* Platforms and Milestone Signs */}
        {chapters.map((ch, idx) => (
          <PlatformNode
            key={ch.id}
            id={ch.id}
            title={ch.title}
            x={ch.platform.x}
            y={ch.platform.y}
            width={ch.platform.width || 180}
            isActive={idx === activeIndex && frame >= timing.jumpEndFrame}
          />
        ))}

        {/* Animated Avatar */}
        <HermesAvatar
          x={charX}
          y={charY}
          isJumping={isJumping}
          facingRight={facingRight}
        />
      </div>

      {/* 3. Watermark-Free Seedance Cutscene Overlay */}
      {hasCutscene && isCutsceneActive && (
        <AbsoluteFill
          style={{
            opacity: cutsceneOpacity,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(0,0,0,0.85)",
            transition: "opacity 0.4s ease",
          }}
        >
          <div
            style={{
              width: 1440,
              height: 810,
              border: "4px solid #ffd700",
              borderRadius: 8,
              overflow: "hidden",
              boxShadow: "0 0 40px rgba(0,0,0,0.9)",
            }}
          >
            <Video
              src={currentChapter.cutscene_video_url!}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
