import React from "react";
import {
  AbsoluteFill,
  Composition,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  bg: "#0b0910",
  panel: "#15111c",
  panelDeep: "#0f0c14",
  line: "#493361",
  text: "#f8f4fb",
  muted: "#b7a9c3",
  violet: "#a77dff",
  amber: "#e5aa56",
  green: "#65d49a",
};

const phases = [
  { label: "WATCHING", detail: "Polling capacity without game input", color: COLORS.violet },
  { label: "SLOT CONFIRMED", detail: "Second sample confirms the open slot", color: COLORS.amber },
  { label: "CONNECTING", detail: "Opening Direct Connect", color: COLORS.violet },
  { label: "JOINED", detail: "Connection accepted", color: COLORS.green },
];

const phaseForFrame = (frame: number) => Math.min(3, Math.floor(frame / 19));

const Step: React.FC<{ label: string; index: number; active: number; color: string }> = ({ label, index, active, color }) => {
  const complete = index < active;
  const current = index === active;
  return (
    <div style={{ width: 152, textAlign: "center", color: complete || current ? COLORS.text : "#79688a", fontSize: 13, fontWeight: 800, letterSpacing: 1.3 }}>
      <div style={{ height: 22, display: "flex", justifyContent: "center", alignItems: "center", position: "relative", zIndex: 1 }}>
        <div style={{ width: 17, height: 17, borderRadius: "50%", backgroundColor: complete || current ? color : "#38284b", border: `3px solid ${COLORS.panel}` }} />
      </div>
      <div style={{ marginTop: 9 }}>{label}</div>
    </div>
  );
};

export const WatchModeWalkthrough: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const active = phaseForFrame(frame);
  const phase = phases[active];
  const intro = spring({ frame, fps, config: { damping: 18, stiffness: 145 } });
  const pulse = 0.92 + Math.sin(frame / 3) * 0.08;
  const logs = [
    "Watching Masternazz Private / 18 of 20 players",
    "Slot candidate detected / confirming",
    "Opening Direct Connect",
    "Joined Masternazz Private",
  ].slice(0, active + 1).reverse();

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, color: COLORS.text, fontFamily: "Segoe UI, Arial, sans-serif", padding: "40px 52px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 15, color: COLORS.violet, fontWeight: 800, letterSpacing: 2.2, fontSize: 15 }}>
        <div style={{ width: 28, height: 28, border: `2px solid ${COLORS.violet}`, borderRadius: 5, transform: "rotate(45deg)", display: "grid", placeItems: "center" }}><span style={{ transform: "rotate(-45deg)", fontSize: 18 }}>S</span></div>
        SCP:SL AUTO-JOINER <span style={{ color: COLORS.muted, fontWeight: 600 }}> / WATCH MODE</span>
      </div>

      <div style={{ marginTop: 29, opacity: intro, transform: `translateY(${interpolate(intro, [0, 1], [16, 0])}px)` }}>
        <div style={{ fontSize: 43, fontWeight: 800, letterSpacing: -1.7 }}>Find the slot. Take the connection.</div>
        <div style={{ marginTop: 8, color: COLORS.muted, fontSize: 19 }}>Monitor quietly until capacity is confirmed.</div>
      </div>

      <div style={{ marginTop: 27, background: COLORS.panel, border: `1px solid ${COLORS.line}`, borderRadius: 13, padding: "21px 24px" }}>
        <div style={{ color: COLORS.violet, fontSize: 12, fontWeight: 800, letterSpacing: 1.8 }}>SAVED DESTINATION</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginTop: 10 }}>
          <div><div style={{ fontSize: 27, fontWeight: 800 }}>Masternazz Private</div><div style={{ marginTop: 5, color: COLORS.muted, fontSize: 15 }}>sanitized.example:7777</div></div>
          <div style={{ color: phase.color, fontSize: 16, fontWeight: 800, letterSpacing: 1.3, transform: `scale(${active === 0 ? pulse : 1})` }}>{phase.label}</div>
        </div>
      </div>

      <div style={{ marginTop: 17, background: COLORS.panel, border: `1px solid ${phase.color}`, borderRadius: 13, overflow: "hidden" }}>
        <div style={{ padding: "18px 24px 15px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ color: COLORS.muted, fontWeight: 800, letterSpacing: 1.7, fontSize: 12 }}>WATCH MODE STATUS</div>
          <div style={{ color: phase.color, fontWeight: 800, letterSpacing: 1.4, fontSize: 15 }}>{phase.label}</div>
        </div>
        <div style={{ padding: "0 31px 14px", display: "flex", justifyContent: "space-between", position: "relative" }}>
          <div style={{ position: "absolute", left: 95, right: 95, top: 10, height: 2, background: COLORS.line }} />
          {['WATCH', 'CONFIRM', 'CONNECT', 'JOIN'].map((label, index) => <Step key={label} label={label} index={index} active={active} color={phase.color} />)}
        </div>
        <div style={{ margin: "0 24px 19px", border: `1px solid ${phase.color}`, borderRadius: 8, padding: "13px 15px", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 11, height: 11, borderRadius: "50%", backgroundColor: phase.color }} />
          <div style={{ fontSize: 16, fontWeight: 700 }}>{phase.detail}</div>
        </div>
        <div style={{ background: COLORS.panelDeep, borderTop: `1px solid ${COLORS.line}`, padding: "13px 24px 17px", minHeight: 111 }}>
          <div style={{ color: COLORS.muted, fontWeight: 800, letterSpacing: 1.6, fontSize: 11 }}>LIVE ACTIVITY</div>
          {logs.map((line, index) => <div key={line} style={{ marginTop: 8, color: index === 0 ? COLORS.text : COLORS.muted, fontFamily: "Consolas, monospace", fontSize: 13 }}>[00:00:0{active - index + 1}] {line}</div>)}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => (
  <Composition id="WatchModeWalkthrough" component={WatchModeWalkthrough} durationInFrames={76} fps={15} width={960} height={640} />
);

export default RemotionRoot;
