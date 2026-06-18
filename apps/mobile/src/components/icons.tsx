import Svg, { Path } from "react-native-svg";

// Hand-drawn line icons matching the demo's 20px / ~2px stroke. Kept minimal and
// stroke-based so they sit as instrument marks, not filled glyphs — and never an
// emoji standing in for an icon.
type IconProps = { size?: number; color: string };

export function ChevronLeft({ size = 20, color }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <Path
        d="M12 4l-6 6 6 6"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

export function FlashOff({ size = 20, color }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <Path
        d="M11 2L4 11h5l-1 7 7-9h-5l1-7z"
        stroke={color}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />
    </Svg>
  );
}
