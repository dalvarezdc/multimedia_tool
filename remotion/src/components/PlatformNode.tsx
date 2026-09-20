import React from "react";

export interface PlatformNodeProps {
  id: number;
  title: string;
  x: number;
  y: number;
  width?: number;
  isActive: boolean;
}

export const PlatformNode: React.FC<PlatformNodeProps> = ({
  title,
  x,
  y,
  width = 180,
  isActive,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: "translate(-50%, -100%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      {/* 1. Wooden Parchment Scroll Sign */}
      <div
        style={{
          padding: "8px 16px",
          marginBottom: 12,
          backgroundColor: isActive ? "#d4a373" : "#4a4e69",
          border: isActive ? "3px solid #ffd700" : "3px solid #22223b",
          boxShadow: isActive
            ? "0 0 16px rgba(255, 215, 0, 0.7), inset 0 0 8px rgba(255, 255, 255, 0.4)"
            : "none",
          borderRadius: 4,
          imageRendering: "pixelated",
          transition: "all 0.3s ease",
          position: "relative",
        }}
      >
        {/* Golden Crosses on Corners */}
        {isActive && (
          <>
            <span style={{ position: "absolute", top: -8, left: -6, color: "#ffd700", fontSize: 14 }}>✦</span>
            <span style={{ position: "absolute", top: -8, right: -6, color: "#ffd700", fontSize: 14 }}>✦</span>
            <span style={{ position: "absolute", bottom: -10, left: -6, color: "#ffd700", fontSize: 14 }}>✦</span>
            <span style={{ position: "absolute", bottom: -10, right: -6, color: "#ffd700", fontSize: 14 }}>✦</span>
          </>
        )}

        <span
          style={{
            fontFamily: "monospace",
            fontWeight: "bold",
            fontSize: 16,
            letterSpacing: 1,
            color: isActive ? "#2b1810" : "#9a8c98",
            textTransform: "uppercase",
          }}
        >
          {title}
        </span>
      </div>

      {/* 2. Floating Stone Brick Platform */}
      <div
        style={{
          width: width,
          height: 36,
          backgroundColor: isActive ? "#2c3e6b" : "#1a233a",
          borderTop: isActive ? "4px solid #486581" : "4px solid #334e68",
          borderBottom: "4px solid #0f172a",
          boxShadow: "0 8px 16px rgba(0,0,0,0.6)",
          display: "flex",
          justifyContent: "space-around",
          alignItems: "center",
          borderRadius: "2px 2px 6px 6px",
        }}
      >
        {/* Decorative Pixel Bricks */}
        <div style={{ width: 30, height: 14, backgroundColor: "#334e68", borderRadius: 1 }} />
        <div style={{ width: 36, height: 14, backgroundColor: "#334e68", borderRadius: 1 }} />
        <div style={{ width: 30, height: 14, backgroundColor: "#334e68", borderRadius: 1 }} />
      </div>
    </div>
  );
};
