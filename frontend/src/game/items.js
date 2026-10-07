import { Armchair, Coffee, Flower2, Lamp, Fence, TreePine, LayoutGrid, Sofa, Bed, BookOpen, Sprout, Disc, Waves, Lightbulb, Flower, Music2 } from "lucide-react";

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
  { id: "bed", name: "Cozy Bed", icon: Bed, color: "#B5C7F5" },
  { id: "rug", name: "Round Rug", icon: Disc, color: "#E8A0BF" },
  { id: "bookshelf", name: "Bookshelf", icon: BookOpen, color: "#9C6B4A" },
  { id: "plant", name: "Potted Plant", icon: Sprout, color: "#3FA34D" },
];

// interior decor palettes
export const FLOORS = {
  wood: { name: "Oak Wood", base: "#C8955B", line: "rgba(92,64,51,0.2)" },
  pink: { name: "Pink Tile", base: "#F3C3D3", line: "rgba(180,100,130,0.25)" },
  mint: { name: "Mint Tile", base: "#BEE6CF", line: "rgba(80,150,110,0.25)" },
  stone: { name: "Stone", base: "#C9C4BC", line: "rgba(80,70,60,0.22)" },
};

export const WALLS = {
  cream: { name: "Cream", base: "#F3D9B5" },
  mint: { name: "Mint", base: "#CDEBD6" },
  blue: { name: "Sky", base: "#CFE4F5" },
  lavender: { name: "Lavender", base: "#E3D6F2" },
};

export const SHOP_ITEMS = [
  { id: "fountain", name: "Fountain", price: 140, icon: Waves, color: "#8ECEF1" },
  { id: "lamppost", name: "Lamp Post", price: 70, icon: Lightbulb, color: "#C9A33A" },
  { id: "arch", name: "Flower Arch", price: 95, icon: Flower, color: "#FF9AA2" },
  { id: "piano", name: "Piano", price: 160, icon: Music2, color: "#5C4033" },
];

export const CROPS = {
  carrot: { name: "Carrot", seedCost: 8, sellPrice: 20, grow: 40, color: "#F0872B", leaf: "#3FA34D" },
  tomato: { name: "Tomato", seedCost: 10, sellPrice: 26, grow: 45, color: "#E8503A", leaf: "#3FA34D" },
  strawberry: { name: "Strawberry", seedCost: 14, sellPrice: 38, grow: 60, color: "#E63950", leaf: "#3FA34D" },
  pumpkin: { name: "Pumpkin", seedCost: 22, sellPrice: 64, grow: 90, color: "#E8822B", leaf: "#3FA34D" },
};

export const ITEM_BY_ID = Object.fromEntries([...ITEMS, ...SHOP_ITEMS].map((i) => [i.id, i]));

export const WORLD = { w: 2000, h: 1500 };
export const HOUSE_WORLD = { w: 900, h: 650 };
export const SPEED = 4.3;
export const PLAYER_R = 18;

export const PONDS = [
  { x: 560, y: 980, rx: 150, ry: 100 },
  { x: 1520, y: 1050, rx: 125, ry: 92 },
  { x: 320, y: 300, rx: 120, ry: 85 },
];

export const TOWN = [
  { id: "shop", name: "Nook Shop", x: 1000, y: 430, color: "#FFE67D", enter: "shop" },
  { id: "museum", name: "Museum", x: 680, y: 470, color: "#C7CEEA", enter: "soon" },
  { id: "cafe", name: "Cafe", x: 1330, y: 500, color: "#FFB899", enter: "soon" },
];

export const SCENERY = [
  { x: 180, y: 300 }, { x: 430, y: 200, s: 1.1 }, { x: 1700, y: 280 }, { x: 1840, y: 520 },
  { x: 160, y: 760 }, { x: 540, y: 1260, s: 1.2 }, { x: 1760, y: 820 }, { x: 1850, y: 1180 },
  { x: 840, y: 250 }, { x: 1180, y: 250 }, { x: 150, y: 1320 }, { x: 1820, y: 1320, s: 1.1 },
  { x: 380, y: 1480 }, { x: 1500, y: 300, s: 0.9 },
];
