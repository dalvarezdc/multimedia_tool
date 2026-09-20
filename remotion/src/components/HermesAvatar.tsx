import React from "react";
import { useCurrentFrame } from "remotion";

export interface HermesAvatarProps {
  x: number;
  y: number;
  isJumping: boolean;
  facingRight?: boolean;
}

export const HermesAvatar: React.FC<HermesAvatarProps> = ({
  x,
  y,
  isJumping,
  facingRight = true,
}) => {
  const frame = useCurrentFrame();

  // Subtle breathing / idle bob
  const idleBob = isJumping ? 0 : Math.sin(frame / 6) * 3;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y + idleBob,
        transform: `translate(-50%, -100%) scaleX(${facingRight ? 1 : -1})`,
        width: 48,
        height: 56,
        imageRendering: "pixelated",
        pointerEvents: "none",
        zIndex: 10,
      }}
    >
      {/* Winged Helmet Wings */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: -8,
          width: 16,
          height: 12,
          backgroundColor: "#ffffff",
          borderRadius: "8px 2px 8px 2px",
          border: "1px solid #d4af37",
          transform: `rotate(${isJumping ? "-20deg" : "-5deg"})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          right: -8,
          width: 16,
          height: 12,
          backgroundColor: "#ffffff",
          borderRadius: "2px 8px 2px 8px",
          border: "1px solid #d4af37",
          transform: `rotate(${isJumping ? "20deg" : "5deg"})`,
        }}
      />

      {/* Golden Helmet & Head */}
      <div
        style={{
          position: "absolute",
          top: 4,
          left: 8,
          width: 32,
          height: 28,
          backgroundColor: "#ffd700",
          borderRadius: "14px 14px 6px 6px",
          border: "2px solid #b8860b",
          overflow: "hidden",
        }}
      >
        {/* Face */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 2,
            width: 24,
            height: 14,
            backgroundColor: "#ffe0bd",
            borderRadius: "0 0 6px 6px",
          }}
        >
          {/* Eyes */}
          <div style={{ position: "absolute", top: 4, left: 6, width: 3, height: 4, backgroundColor: "#2b1810" }} />
          <div style={{ position: "absolute", top: 4, right: 6, width: 3, height: 4, backgroundColor: "#2b1810" }} />
        </div>
      </div>

      {/* Body & Blue Tunic */}
      <div
        style={{
          position: "absolute",
          top: 32,
          left: 12,
          width: 24,
          height: 20,
          backgroundColor: "#2563eb",
          borderRadius: "4px 4px 6px 6px",
          border: "1px solid #1e3a8a",
        }}
      />

      {/* Golden Caduceus Staff */}
      <div
        style={{
          position: "absolute",
          top: 14,
          right: 2,
          width: 4,
          height: 38,
          backgroundColor: "#ffd700",
          borderRadius: 2,
          border: "1px solid #b8860b",
          transform: "rotate(10deg)",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -4,
            left: -4,
            width: 12,
            height: 8,
            backgroundColor: "#ffd700",
            borderRadius: "50%",
            border: "1px solid #b8860b",
          }}
        />
      </div>
    </div>
  );
};
