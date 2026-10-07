import { Armchair, Coffee, Flower2, Lamp, Fence, TreePine, LayoutGrid, Sofa } from "lucide-react";

export const AVATAR_COLORS = [
  { name: "Peach Sunset", hex: "#FF9AA2", border: "#E06873" },
  { name: "Butter Cream", hex: "#FFDAC1", border: "#E5AF8C" },
  { name: "Mint Meadow", hex: "#B5EAD7", border: "#7CC9B0" },
  { name: "Sky Breeze", hex: "#C7CEEA", border: "#8F9BC7" },
  { name: "Leaf Green", hex: "#E2F0CB", border: "#ADC887" },
  { name: "Coral Blossom", hex: "#FFB7B2", border: "#D87F79" },
];

// icon used in HUD; color/shape used on canvas
export const ITEMS = [
  { id: "chair", name: "Wood Chair", icon: Armchair, color: "#C89B6E" },
  { id: "table", name: "Wooden Table", icon: Coffee, color: "#A9744F" },
  { id: "flower", name: "Flower Pot", icon: Flower2, color: "#FF8FA3" },
  { id: "lamp", name: "Cozy Lamp", icon: Lamp, color: "#FFD95A" },
  { id: "fence", name: "Wooden Fence", icon: Fence, color: "#D2B48C" },
  { id: "tree", name: "Fruit Tree", icon: TreePine, color: "#4CAF50" },
  { id: "blanket", name: "Picnic Blanket", icon: LayoutGrid, color: "#FFB7B2" },
  { id: "bench", name: "Garden Bench", icon: Sofa, color: "#8ECEF1" },
];

export const ITEM_BY_ID = Object.fromEntries(ITEMS.map((i) => [i.id, i]));

export const WORLD = { w: 2000, h: 1500 };
export const HOUSE_WORLD = { w: 900, h: 650 };
export const SPEED = 3.2;
export const PLAYER_R = 18;
