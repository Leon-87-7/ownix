// Curated Lucide icons a space may use. Single source of truth shared by the
// icon picker (#191) and the space card (#190). Keep in sync with the backend
// SpaceIcon Literal in src/api/spaces.py.
import {
  Folder, Star, Bookmark, Globe, Zap, Heart, Code, Music, Film, Camera,
  Coffee, Flame, Rocket, Target, Compass, Anchor, Crown, Diamond, Shield, Lightbulb,
} from "lucide-react";

type IconCmp = typeof Folder;

export const SPACE_ICONS: { name: string; Icon: IconCmp }[] = [
  { name: "folder", Icon: Folder },
  { name: "star", Icon: Star },
  { name: "bookmark", Icon: Bookmark },
  { name: "globe", Icon: Globe },
  { name: "zap", Icon: Zap },
  { name: "heart", Icon: Heart },
  { name: "code", Icon: Code },
  { name: "music", Icon: Music },
  { name: "film", Icon: Film },
  { name: "camera", Icon: Camera },
  { name: "coffee", Icon: Coffee },
  { name: "flame", Icon: Flame },
  { name: "rocket", Icon: Rocket },
  { name: "target", Icon: Target },
  { name: "compass", Icon: Compass },
  { name: "anchor", Icon: Anchor },
  { name: "crown", Icon: Crown },
  { name: "diamond", Icon: Diamond },
  { name: "shield", Icon: Shield },
  { name: "lightbulb", Icon: Lightbulb },
];

export const DEFAULT_SPACE_ICON: IconCmp = Folder;

// Resolve `<Icon />` via SPACE_ICON_BY_NAME[name] ?? DEFAULT_SPACE_ICON, not a
// function call — react-hooks/static-components flags a component variable
// assigned from a CallExpression as "created during render", even when (as
// here) the lookup is pure and reference-stable.
export const SPACE_ICON_BY_NAME: Record<string, IconCmp> = Object.fromEntries(
  SPACE_ICONS.map(({ name, Icon }) => [name, Icon]),
);
