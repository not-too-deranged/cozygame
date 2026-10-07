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
- Lobby, real-time shared world, chat, emotes, houses & interiors, decor, rotation, more furniture, door walk-through (iterations 1-3).
- Bells economy: each player starts with 120 bells, persisted per (room, player) in player_state; wallet synced privately.
- Farming: buy seeds (carrot/tomato/strawberry/pumpkin) at Shop, Plant in front of you, crops grow over real time (40-90s), Harvest (H) when ripe (✨), held crops sold for bells. Server validates ripeness & rejects overspend/invalid actions.
- Shop: Buy tab (seeds + 4 special unlockable furniture: fountain/lamppost/arch/piano that add to your toolbar) and Sell Harvest tab.
- Day/Night cycle: shared 8-min sky cycle on the island (morning→midday→sunset→dusk→night) with stars + moon; HUD clock badge.
- Startup Mongo indexes (unique player_state & houses, room code) to prevent duplicate wallets/houses.
- All verified by testing agent iteration_4 (100%; 25/25 backend tests green).

## Backlog (P1/P2)
- P1: Furniture rotation (R key), collision, item ownership/lock rules.
- P1: Player customization (hats/outfits), more furniture types & floor/wallpaper choices.
- P2: Day/night cycle, fishing/bug catching mini-games, museum.
- P2: Per-player inventory economy (currency, shop). House spoofing hardening if ever non-MVP.
- Tech debt: IslandGame.jsx ~835 lines — consider splitting rendering/game-loop module.

## Next Tasks
- Gather feedback after first multiplayer session with friends.
