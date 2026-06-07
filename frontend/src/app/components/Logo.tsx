import { ImageWithFallback } from "./figma/ImageWithFallback";
import logoImg from "../../imports/deep-research.png";

export function Logo({ size = 28 }: { size?: number }) {
  const imgSize = Math.round(size * 0.68);
  return (
    <div className="flex items-center gap-2">
      <div
        className="rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ width: size, height: size, background: "#000" }}
      >
        <ImageWithFallback
          src={logoImg}
          alt="dataAgent"
          className="object-contain"
          style={{ width: imgSize, height: imgSize }}
        />
      </div>
      <span style={{ color: "var(--ink-900)", fontWeight: 700, letterSpacing: "-0.025em", fontSize: "14.5px" }}>
        DataAgent
      </span>
    </div>
  );
}
