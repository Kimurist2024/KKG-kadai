import type { SegmentOut } from "../../types";
import { fmt } from "../../format";

interface Props {
  segments: SegmentOut[];
  highlight: Set<number>;
  unitsPerPx: number;
  color: string;
  strokeWidth: number;
  highlightedStrokeWidth: number;
  haloWidth: number;
  opacity: number;
  keyPrefix: "w" | "d";
  titleKind: "壁" | "ドア";
}

export default function DetectedSegmentLayer({ segments, highlight, unitsPerPx, color, strokeWidth, highlightedStrokeWidth, haloWidth, opacity, keyPrefix, titleKind }: Props) {
  return (
    <>
      {segments.map((segment) => (
        <g key={`${keyPrefix}${segment.id}`} pointerEvents="none">
          {highlight.has(segment.id) && <line x1={segment.start.x} y1={segment.start.y} x2={segment.end.x} y2={segment.end.y} stroke="#fff" strokeWidth={haloWidth * unitsPerPx} strokeLinecap="round" />}
          <line x1={segment.start.x} y1={segment.start.y} x2={segment.end.x} y2={segment.end.y} stroke={color} strokeWidth={(highlight.has(segment.id) ? highlightedStrokeWidth : strokeWidth) * unitsPerPx} strokeLinecap="round" opacity={highlight.size && !highlight.has(segment.id) ? 0.45 : opacity}>
            <title>{`${titleKind} id=${segment.id}  ${fmt(segment.length_m)} m (${fmt(segment.length_px, 1)} px)`}</title>
          </line>
        </g>
      ))}
    </>
  );
}
