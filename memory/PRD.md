# Cozy Island — PRD

## Original Problem Statement
"I would like to build a game like Animal Crossing for me and my 2 friends to play together on a Macbook each."

## User Choices
- Shared island + avatars, walk around, chat, place/collect items
- Live shared world (real-time, see each other move)
- Cute top-down 2D pastel style
- Join via name + shared room code (no accounts)
- Progress (island state & chat) saved in MongoDB

## Architecture
- **Frontend**: React 19 + Vite + Tailwind v4. HTML5 Canvas game world (top-down). HUD overlays with shadcn/framer-motion. Font: Fredoka + Nunito. Web Audio synth sfx.
- **Backend**: FastAPI + MongoDB. REST for room create/get. WebSocket `/api/ws/{code}` for real-time: join, move, chat, place, pickup (broadcast per room).
- **Persistence**: `rooms`, `items` (placed furniture), `chat` collections. Player live positions are in-memory per room hub.

## Implemented (2026-10-07)
- Lobby: name, avatar color picker, create/join tabs, room code validation.
- Real-time shared world: players see each other move, join/leave toasts, name tags.
- Island chat (persisted, last 50 loaded on join).
- Inventory of 8 furniture items; place (E) in facing direction, pick up (F) nearest.
- Placed items persist in DB and sync to all players.
- Room code badge (copy), player roster modal, connection status, leave.
- Player emotes: 8-reaction picker, floating bubble above avatar, zone-scoped broadcast.
- Houses & interiors (zones): Build House on island (one per player, nameplate), Enter/visit any house, decorate interior with furniture. Items/presence/movement are zone-isolated (island vs house:<ownerId>). Interiors persist and are visible to fresh joiners.
- Floor & Wallpaper decor: owner-only per-house floor (wood/pink/mint/stone) + wall (cream/mint/blue/lavender), persisted and synced to visitors in that house (server-side allowlisted).
- Furniture rotation: R key / Rotate button cycles 0/90/180/270 (server-normalized), applied on placement and persisted.
- More furniture: 12 total items (added Bed, Rug, Bookshelf, Potted Plant); toolbar scrolls.
- Door walk-through: walk into a house door to enter; walk onto the interior EXIT mat to leave; exiting spawns you just in front of your house. Enter/Exit buttons also remain.
- All verified by testing agent iterations 2 & 3 (100%; 18 backend tests green).

## Backlog (P1/P2)
- P1: Furniture rotation (R key), collision, item ownership/lock rules.
- P1: Player customization (hats/outfits), more furniture types & floor/wallpaper choices.
- P2: Day/night cycle, fishing/bug catching mini-games, museum.
- P2: Per-player inventory economy (currency, shop). House spoofing hardening if ever non-MVP.
- Tech debt: IslandGame.jsx ~835 lines — consider splitting rendering/game-loop module.

## Next Tasks
- Gather feedback after first multiplayer session with friends.
