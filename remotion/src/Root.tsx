import React from "react";
import { Composition } from "remotion";
import { MasterRoadmapVideo } from "./compositions/MasterRoadmapVideo";

const defaultStoryboard = {
  theme: "greek_night_sky",
  chapters: [
    {
      id: 1,
      title: "Hardware Choices",
      narration_text: "Selecting compute hardware for running models locally.",
      platform: { x: 300, y: 550, width: 200 },
      seedance_prompt: "Cinematic shot of neon futuristic server racks...",
      duration_seconds: 5,
    },
    {
      id: 2,
      title: "Download & Setup",
      narration_text: "Installing runtimes and dependencies.",
      platform: { x: 750, y: 460, width: 200 },
      seedance_prompt: "Futuristic terminal interface downloading packages...",
      duration_seconds: 5,
    },
    {
      id: 3,
      title: "Features",
      narration_text: "Exploring foundational model capabilities.",
      platform: { x: 1200, y: 580, width: 200 },
      seedance_prompt: "Glowing neural network synapsing and connecting...",
      duration_seconds: 5,
    },
    {
      id: 4,
      title: "Memory System",
      narration_text: "Managing context windows and memory retrieval.",
      platform: { x: 1650, y: 440, width: 200 },
      seedance_prompt: "Crystalline memory cubes organizing in 3D space...",
      duration_seconds: 5,
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  // 4 chapters * ~6.2 seconds = ~25 seconds = 1500 frames at 60 fps
  return (
    <Composition
      id="MasterRoadmapVideo"
      component={MasterRoadmapVideo}
      durationInFrames={1500}
      fps={60}
      width={1920}
      height={1080}
      defaultProps={{
        storyboard: defaultStoryboard,
      }}
    />
  );
};
