import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";

export interface ParallaxBackgroundProps {
  cameraX: number;
}

export const ParallaxBackground: React.FC<ParallaxBackgroundProps> = ({ cameraX }) => {
  const frame = useCurrentFrame();

  // Slow parallax factor for deep sky (stars)
  const skyOffset = -cameraX * 0.1;
  // Medium parallax factor for distant castle/ruins
  const midgroundOffset = -cameraX * 0.35;

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#060919" }}>
      {/* 1. Deep Space Night Sky with Procedural Twinkling Stars */}
      <div
        style={{
          position: "absolute",
          width: "140%",
          height: "100%",
          transform: `translateX(${skyOffset}px)`,
          backgroundImage: `
            radial-gradient(1px 1px at 40px 60px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 120px 180px, #b0c8ff, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 280px 90px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 420px 240px, #ffd700, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 600px 70px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 780px 200px, #90b8ff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 950px 110px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 1100px 290px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 1350px 80px, #ffd700, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 1600px 220px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 1800px 150px, #b0c8ff, rgba(0,0,0,0))
          `,
          opacity: 0.8 + 0.2 * Math.sin(frame / 12),
        }}
      />

      {/* 2. Distant Ruined Mountain & Castle Silhouette */}
      <svg
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "160%",
          height: 480,
          transform: `translateX(${midgroundOffset}px)`,
        }}
        viewBox="0 0 2500 500"
        preserveAspectRatio="none"
      >
        <path
          d="M0,500 L0,320 L150,280 L320,350 L480,260 L620,310 L750,180 L820,180 L850,240 L1020,300 L1200,210 L1400,340 L1600,270 L1780,310 L1950,190 L2100,260 L2300,310 L2500,290 L2500,500 Z"
          fill="#0c1438"
        />
        <path
          d="M0,500 L0,380 L200,340 L400,390 L600,320 L800,360 L1000,290 L1200,350 L1450,300 L1700,370 L1950,310 L2200,380 L2500,340 L2500,500 Z"
          fill="#111c4e"
        />
      </svg>
    </AbsoluteFill>
  );
};
