import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Copy, Users, LogOut, Send, MessageCircle, X, Hand, Smile, Home, DoorOpen, Hammer } from "lucide-react";
import { ITEMS, ITEM_BY_ID, WORLD, HOUSE_WORLD, SPEED, PLAYER_R } from "@/game/items";

const EMOTES = ["👋", "😂", "❤️", "😮", "😎", "🎉", "😢", "🌸"];

import { sfx } from "@/game/sound";

const WS_BASE = process.env.REACT_APP_BACKEND_URL.replace(/^http/, "ws");

export default function IslandGame({ code, player, onLeave }) {
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const meRef = useRef({ ...player, x: 1000, y: 750, dir: "down" });
  const playersRef = useRef({}); // id -> player (others)
  const itemsRef = useRef([]); // placed items
  const emotesRef = useRef({}); // id -> { emote, until }
  const housesRef = useRef([]);
  const zoneRef = useRef("island");
  const worldRef = useRef(WORLD);
  const keysRef = useRef({});
  const camRef = useRef({ x: 0, y: 0 });
  const lastSentRef = useRef(0);
  const chatOpenRef = useRef(false);

  const [connected, setConnected] = useState(false);
  const [roster, setRoster] = useState([player]);
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatOpen, setChatOpen] = useState(true);
  const [showRoster, setShowRoster] = useState(false);
  const [emotePicker, setEmotePicker] = useState(false);
  const [zone, setZone] = useState("island");
  const [hasHouse, setHasHouse] = useState(false);
  const [houseOwner, setHouseOwner] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(0);
  const selectedSlotRef = useRef(0);
  const chatInputRef = useRef(null);
  const chatBoxRef = useRef(null);

  const addChat = useCallback((m) => setChat((c) => [...c.slice(-80), m]), []);

  // ---------- WebSocket ----------
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/api/ws/${code}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: "join", player }));
    };
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      switch (msg.type) {
        case "init": {
          meRef.current = { ...meRef.current, ...msg.you };
          itemsRef.current = msg.items || [];
          housesRef.current = msg.houses || [];
          setHasHouse((msg.houses || []).some((h) => h.owner_id === msg.you.id));
          setChat((msg.chat || []).map((m) => ({ ...m })));
          const others = {};
          (msg.players || []).forEach((p) => {
            if (p.id !== msg.you.id) others[p.id] = p;
          });
          playersRef.current = others;
          setRoster([msg.you, ...Object.values(others)]);
          break;
        }
        case "zone_state": {
          zoneRef.current = msg.zone;
          worldRef.current = msg.zone === "island" ? WORLD : HOUSE_WORLD;
          setZone(msg.zone);
          meRef.current = { ...meRef.current, ...msg.you };
          itemsRef.current = msg.items || [];
          housesRef.current = msg.houses || housesRef.current;
          emotesRef.current = {};
          const o2 = {};
          (msg.players || []).forEach((p) => {
            if (p.id !== meRef.current.id) o2[p.id] = p;
          });
          playersRef.current = o2;
          setRoster([meRef.current, ...Object.values(o2)]);
          break;
        }
        case "house":
          housesRef.current = [...housesRef.current.filter((h) => h.owner_id !== msg.house.owner_id), msg.house];
          if (msg.house.owner_id === meRef.current.id) setHasHouse(true);
          break;
        case "players":
          setRoster(msg.players);
          msg.players.forEach((p) => {
            if (p.id !== meRef.current.id && !playersRef.current[p.id]) {
              playersRef.current[p.id] = p;
            }
          });
          Object.keys(playersRef.current).forEach((id) => {
            if (!msg.players.find((p) => p.id === id)) delete playersRef.current[id];
          });
          break;
        case "player_join":
          if (msg.player.id !== meRef.current.id) {
            playersRef.current[msg.player.id] = msg.player;
            sfx.join();
            toast(`${msg.player.name} arrived on the island! 🌴`);
          }
          break;
        case "player_leave":
          delete playersRef.current[msg.id];
          break;
        case "move": {
          const p = playersRef.current[msg.id];
          if (p) { p.x = msg.x; p.y = msg.y; p.dir = msg.dir; }
          break;
        }
        case "chat":
          addChat(msg.message);
          if (msg.message.player !== meRef.current.name) sfx.chat();
          break;
        case "place":
          itemsRef.current = [...itemsRef.current, msg.item];
          break;
        case "pickup":
          itemsRef.current = itemsRef.current.filter((i) => i.id !== msg.itemId);
          break;
        case "emote":
          emotesRef.current[msg.id] = { emote: msg.emote, until: performance.now() + 2200 };
          break;
        default:
          break;
      }
    };
    return () => ws.close();
    // eslint-disable-next-line
  }, [code]);

  useEffect(() => {
    if (chatBoxRef.current) chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
  }, [chat]);

  // ---------- Input ----------
  useEffect(() => {
    const down = (e) => {
      const k = e.key.toLowerCase();
      if (chatOpenRef.current && document.activeElement === chatInputRef.current) {
        if (k === "escape") chatInputRef.current.blur();
        return;
      }
      if (k === "enter") { e.preventDefault(); focusChat(); return; }
      if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright"].includes(k)) {
        keysRef.current[k] = true;
        e.preventDefault();
      }
      if (k >= "1" && k <= "8") selectSlot(parseInt(k, 10) - 1);
      if (k === "e") placeItem();
      if (k === "f") pickupItem();
      if (k === "escape") setShowRoster(false);
    };
    const up = (e) => { keysRef.current[e.key.toLowerCase()] = false; };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
    // eslint-disable-next-line
  }, []);

  const focusChat = () => {
    setChatOpen(true);
    chatOpenRef.current = true;
    setTimeout(() => chatInputRef.current?.focus(), 50);
  };

  const selectSlot = (i) => { setSelectedSlot(i); selectedSlotRef.current = i; sfx.click(); };

  const send = (obj) => {
    if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify(obj));
  };

  const placeItem = () => {
    const me = meRef.current;
    const off = 50;
    const d = me.dir;
    const x = me.x + (d === "left" ? -off : d === "right" ? off : 0);
    const y = me.y + (d === "up" ? -off : d === "down" ? off : 0);
    const itemType = ITEMS[selectedSlotRef.current].id;
    send({ type: "place", itemType, x, y });
    sfx.place();
  };

  const pickupItem = () => {
    const me = meRef.current;
    let nearest = null, best = 70 * 70;
    for (const it of itemsRef.current) {
      const dx = it.x - me.x, dy = it.y - me.y;
      const dsq = dx * dx + dy * dy;
      if (dsq < best) { best = dsq; nearest = it; }
    }
    if (nearest) { send({ type: "pickup", itemId: nearest.id }); sfx.pickup(); }
  };

  const sendChat = () => {
    const t = chatInput.trim();
    if (!t) return;
    send({ type: "chat", text: t });
    setChatInput("");
  };

  const sendEmote = (emote) => {
    emotesRef.current[meRef.current.id] = { emote, until: performance.now() + 2200 };
    send({ type: "emote", emote });
    sfx.pop();
    setEmotePicker(false);
  };

  const buildHouse = () => {
    send({ type: "build_house" });
    sfx.place();
    toast.success("Your house is built! 🏠 Walk up to it and tap Enter.");
  };

  const enterHouse = () => {
    const me = meRef.current;
    let nearest = null, best = 150 * 150;
    for (const h of housesRef.current) {
      const dx = h.x - me.x, dy = h.y - me.y, dsq = dx * dx + dy * dy;
      if (dsq < best) { best = dsq; nearest = h; }
    }
    if (nearest) {
      setHouseOwner(nearest.owner_name);
      send({ type: "enter_zone", zone: `house:${nearest.owner_id}` });
      sfx.pop();
    } else {
      toast("Walk closer to a house to go inside! 🚪");
    }
  };

  const exitHouse = () => {
    setHouseOwner(null);
    send({ type: "enter_zone", zone: "island" });
    sfx.pop();
  };

  const copyCode = () => {
    navigator.clipboard?.writeText(code);
    sfx.pop();
    toast.success(`Room code ${code} copied!`);
  };

  // ---------- Game loop ----------
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    let raf;
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const loop = (t) => {
      const me = meRef.current;
      const k = keysRef.current;
      let dx = 0, dy = 0;
      if (k.w || k.arrowup) dy -= 1;
      if (k.s || k.arrowdown) dy += 1;
      if (k.a || k.arrowleft) dx -= 1;
      if (k.d || k.arrowright) dx += 1;
      if (dx || dy) {
        const len = Math.hypot(dx, dy) || 1;
        const world = worldRef.current;
        me.x = Math.max(40, Math.min(world.w - 40, me.x + (dx / len) * SPEED));
        me.y = Math.max(40, Math.min(world.h - 40, me.y + (dy / len) * SPEED));
        me.dir = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
        me.moving = true;
        if (t - lastSentRef.current > 60) {
          lastSentRef.current = t;
          send({ type: "move", x: me.x, y: me.y, dir: me.dir });
        }
      } else {
        me.moving = false;
      }

      // camera
      const cam = camRef.current;
      const world = worldRef.current;
      cam.x = me.x - canvas.width / 2;
      cam.y = me.y - canvas.height / 2;
      cam.x = Math.max(0, Math.min(world.w - canvas.width, cam.x));
      cam.y = Math.max(0, Math.min(world.h - canvas.height, cam.y));
      if (world.w < canvas.width) cam.x = (world.w - canvas.width) / 2;
      if (world.h < canvas.height) cam.y = (world.h - canvas.height) / 2;

      render(ctx, canvas, cam, me, playersRef.current, itemsRef.current, emotesRef.current, housesRef.current, zoneRef.current, t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
    // eslint-disable-next-line
  }, []);

  const SlotIcon = ITEMS[selectedSlot].icon;

  return (
    <div className="w-screen h-screen overflow-hidden relative bg-[#7BC676] select-none font-['Nunito']">
      <canvas ref={canvasRef} className="absolute inset-0 z-0" data-testid="game-canvas" />

      {/* Top bar */}
      <div className="absolute top-4 left-4 right-4 flex justify-between items-start z-40 pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <button
            data-testid="room-code-badge"
            onClick={copyCode}
            className="bg-[#FFFBF4] border-[3px] border-[#5C4033] px-4 py-2 rounded-full font-['Fredoka'] font-bold text-[#5C4033] shadow-[0_4px_0_#5C4033] flex items-center gap-2 hover:scale-105 transition-transform"
          >
            <span className="text-xs uppercase tracking-wider text-[#A0836C]">Code</span>
            <span className="tracking-widest">{code}</span>
            <Copy className="w-4 h-4" />
          </button>
          <button
            data-testid="players-badge"
            onClick={() => { setShowRoster(true); sfx.click(); }}
            className="bg-[#FFFBF4] border-[3px] border-[#5C4033] px-4 py-2 rounded-full font-['Fredoka'] font-bold text-[#5C4033] shadow-[0_4px_0_#5C4033] flex items-center gap-2 hover:scale-105 transition-transform"
          >
            <Users className="w-4 h-4" /> {roster.length}
          </button>
          <span
            className={`px-3 py-2 rounded-full text-xs font-bold font-['Fredoka'] border-[3px] shadow-[0_4px_0_rgba(92,64,51,0.3)] ${
              connected ? "bg-[#DDF5D6] text-[#2D5A27] border-[#3A8037]" : "bg-[#FFE0E0] text-[#B0443C] border-[#D87F79]"
            }`}
            data-testid="connection-status"
          >
            {connected ? "● Live" : "○ Connecting"}
          </span>
        </div>
        <button
          data-testid="leave-button"
          onClick={() => { sfx.click(); onLeave(); }}
          className="pointer-events-auto bg-[#FFB7B2] border-[3px] border-[#D87F79] px-4 py-2 rounded-full font-['Fredoka'] font-bold text-[#8A2B23] shadow-[0_4px_0_#D87F79] flex items-center gap-2 hover:scale-105 active:translate-y-0.5 transition-all"
        >
          <LogOut className="w-4 h-4" /> Leave
        </button>
      </div>

      {/* Chat */}
      <div className="absolute bottom-28 left-4 z-40 pointer-events-auto w-[86vw] max-w-80">
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="bg-[#FFFBF4]/95 backdrop-blur-md border-[3px] border-[#5C4033] rounded-3xl p-3 shadow-[0_6px_0_rgba(92,64,51,0.2)] flex flex-col gap-2 mb-2"
              data-testid="chat-panel"
            >
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-bold uppercase tracking-wider text-[#7C5A3E] flex items-center gap-1">
                  <MessageCircle className="w-3.5 h-3.5" /> Island Chat
                </span>
                <button data-testid="chat-close" onClick={() => { setChatOpen(false); chatOpenRef.current = false; }}>
                  <X className="w-4 h-4 text-[#A0836C]" />
                </button>
              </div>
              <div ref={chatBoxRef} className="h-36 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar" data-testid="chat-messages">
                {chat.length === 0 && (
                  <p className="text-xs text-[#A0836C] font-semibold text-center py-4">Say hi to your friends! 👋</p>
                )}
                {chat.map((m, i) => (
                  <div key={i} className="p-2 px-2.5 rounded-2xl bg-[#FAF0E4] border border-[#5C4033]/15 text-xs font-semibold text-[#3D271D] leading-snug">
                    <span className="font-extrabold font-['Fredoka']" style={{ color: m.color || "#5C4033" }}>{m.player}: </span>
                    {m.text}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="flex items-center gap-2 bg-[#FAF0E4] border-[3px] border-[#5C4033] rounded-full px-3 py-1.5 focus-within:ring-2 focus-within:ring-[#9ED89D] shadow-[0_4px_0_rgba(92,64,51,0.2)]">
          <input
            ref={chatInputRef}
            data-testid="chat-input-field"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onFocus={() => { chatOpenRef.current = true; setChatOpen(true); }}
            onBlur={() => { chatOpenRef.current = false; }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); sendChat(); } }}
            maxLength={200}
            placeholder="Press Enter to chat..."
            className="flex-1 bg-transparent outline-none text-sm font-semibold text-[#3D271D] placeholder-[#A0836C] min-w-0"
          />
          <button data-testid="chat-send" onClick={sendChat} className="text-[#4CAF50] hover:scale-110 transition-transform shrink-0">
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Placement controls */}
      <div className="absolute bottom-28 right-4 z-40 pointer-events-auto flex flex-col gap-2 items-end">
        {zone === "island" ? (
          <>
            {!hasHouse && (
              <button
                data-testid="build-house-button"
                onClick={buildHouse}
                className="bg-[#FFB899] text-[#6B2E17] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#D87F57] shadow-[0_4px_0_#D87F57] flex items-center gap-2 hover:brightness-105 active:translate-y-0.5 active:shadow-[0_1px_0_#D87F57] transition-all"
              >
                <Hammer className="w-4 h-4" /> Build House
              </button>
            )}
            <button
              data-testid="enter-house-button"
              onClick={enterHouse}
              className="bg-[#8ECEF1] text-[#0F4C66] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#4FA3C9] shadow-[0_4px_0_#4FA3C9] flex items-center gap-2 hover:brightness-105 active:translate-y-0.5 active:shadow-[0_1px_0_#4FA3C9] transition-all"
            >
              <DoorOpen className="w-4 h-4" /> Enter House
            </button>
          </>
        ) : (
          <button
            data-testid="exit-house-button"
            onClick={exitHouse}
            className="bg-[#8ECEF1] text-[#0F4C66] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#4FA3C9] shadow-[0_4px_0_#4FA3C9] flex items-center gap-2 hover:brightness-105 active:translate-y-0.5 active:shadow-[0_1px_0_#4FA3C9] transition-all"
          >
            <LogOut className="w-4 h-4" /> Exit to Island
          </button>
        )}
        <AnimatePresence>
          {emotePicker && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8, y: 10 }}
              className="bg-[#FFFBF4] border-[3px] border-[#5C4033] rounded-3xl p-2 shadow-[0_6px_0_rgba(92,64,51,0.2)] grid grid-cols-4 gap-1.5"
              data-testid="emote-picker"
            >
              {EMOTES.map((e) => (
                <button
                  key={e}
                  data-testid={`emote-${e}`}
                  onClick={() => sendEmote(e)}
                  className="w-10 h-10 text-2xl rounded-xl bg-[#FAF0E4] border-2 border-[#5C4033]/20 hover:bg-[#FFE67D] hover:scale-110 active:scale-95 transition-all flex items-center justify-center"
                >
                  {e}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        <button
          data-testid="emote-button"
          onClick={() => { setEmotePicker((v) => !v); sfx.click(); }}
          className="bg-[#D3B6ED] text-[#4A2E6B] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#A97FD6] shadow-[0_4px_0_#A97FD6] flex items-center gap-2 hover:brightness-105 active:translate-y-0.5 active:shadow-[0_1px_0_#A97FD6] transition-all"
        >
          <Smile className="w-4 h-4" /> Emote
        </button>
        <button
          data-testid="place-button"
          onClick={placeItem}
          className="bg-[#9ED89D] text-[#1E431B] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#3A8037] shadow-[0_4px_0_#3A8037] flex items-center gap-2 hover:bg-[#B0E8AF] active:translate-y-0.5 active:shadow-[0_1px_0_#3A8037] transition-all"
        >
          <SlotIcon className="w-4 h-4" /> Place <kbd className="bg-[#3A8037]/20 px-1.5 rounded text-xs">E</kbd>
        </button>
        <button
          data-testid="pickup-button"
          onClick={pickupItem}
          className="bg-[#FFE67D] text-[#6B4E12] font-['Fredoka'] font-bold text-sm px-4 py-2.5 rounded-2xl border-[3px] border-[#C9A33A] shadow-[0_4px_0_#C9A33A] flex items-center gap-2 hover:brightness-105 active:translate-y-0.5 active:shadow-[0_1px_0_#C9A33A] transition-all"
        >
          <Hand className="w-4 h-4" /> Pick Up <kbd className="bg-[#C9A33A]/30 px-1.5 rounded text-xs">F</kbd>
        </button>
      </div>

      {/* Inventory toolbar */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 pointer-events-auto">
        <div className="bg-[#FFFBF4] border-4 border-[#5C4033] p-2 rounded-[28px] shadow-[0_8px_0_rgba(92,64,51,0.2)] flex items-center gap-1.5 sm:gap-2" data-testid="inventory-toolbar">
          {ITEMS.map((it, i) => {
            const Icon = it.icon;
            const active = selectedSlot === i;
            return (
              <button
                key={it.id}
                data-testid={`inventory-slot-${i + 1}`}
                onClick={() => selectSlot(i)}
                title={it.name}
                className={`w-11 h-11 sm:w-14 sm:h-14 rounded-2xl flex flex-col items-center justify-center relative transition-all ${
                  active
                    ? "bg-[#FFE67D] border-[3px] border-[#5C4033] shadow-[0_4px_0_#5C4033] -translate-y-1.5 scale-110"
                    : "bg-[#FAF0E4] border-[3px] border-[#5C4033]/30 hover:border-[#5C4033] hover:scale-105"
                }`}
              >
                <Icon className="w-5 h-5 sm:w-6 sm:h-6" style={{ color: it.color }} strokeWidth={2.5} />
                <span className="absolute -top-2 -right-1.5 bg-[#5C4033] text-[#FFFBF4] text-[9px] font-extrabold font-['Fredoka'] w-4 h-4 flex items-center justify-center rounded-full border border-[#FFFBF4]">
                  {i + 1}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Roster modal */}
      <AnimatePresence>
        {showRoster && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-[#3D271D]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowRoster(false)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-[#FFFBF4] border-4 border-[#5C4033] rounded-[32px] max-w-md w-full p-6 shadow-[0_12px_0_#5C4033]"
              data-testid="roster-modal"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-[#4A3525] font-['Fredoka'] flex items-center gap-2">
                  <Users className="w-5 h-5" /> On the Island
                </h2>
                <button data-testid="roster-close" onClick={() => setShowRoster(false)}>
                  <X className="w-5 h-5 text-[#A0836C]" />
                </button>
              </div>
              <div className="space-y-2">
                {roster.map((p) => (
                  <div key={p.id} className="flex items-center gap-3 bg-[#FAF0E4] border-2 border-[#5C4033]/15 rounded-2xl p-2.5" data-testid={`roster-item-${p.id}`}>
                    <div className="w-9 h-9 rounded-full border-[3px] shrink-0" style={{ background: p.color, borderColor: p.border }} />
                    <span className="font-bold font-['Fredoka'] text-[#3D271D]">{p.name}</span>
                    {p.id === meRef.current.id && (
                      <span className="ml-auto text-xs font-bold text-[#4CAF50] bg-[#DDF5D6] px-2 py-0.5 rounded-full">You</span>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Controls hint */}
      <div className="absolute top-20 left-4 z-30 pointer-events-none bg-[#FFFBF4]/85 border-2 border-[#5C4033]/20 rounded-2xl px-3 py-1.5 text-[11px] font-bold text-[#7C5A3E] font-['Fredoka']">
        WASD / Arrows to move · 1–8 items · E place · F pick up
      </div>

      {/* Interior banner */}
      {zone !== "island" && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-30 pointer-events-none bg-[#FFF3DF] border-[3px] border-[#5C4033] rounded-full px-5 py-2 text-sm font-bold text-[#5C4033] font-['Fredoka'] shadow-[0_4px_0_#5C4033] flex items-center gap-2" data-testid="interior-banner">
          <Home className="w-4 h-4" /> Inside {houseOwner ? `${houseOwner}'s` : "a"} House — decorate freely!
        </div>
      )}
    </div>
  );
}

// ---------- Rendering ----------
function render(ctx, canvas, cam, me, others, items, emotes, houses, zone, t) {
  if (zone === "island") drawIsland(ctx, canvas, cam);
  else drawInterior(ctx, canvas, cam);

  if (zone === "island") {
    const hs = [...houses].sort((a, b) => a.y - b.y);
    for (const h of hs) drawHouse(ctx, h, cam, me.id);
  }

  // placed items (sorted by y for depth)
  const sorted = [...items].sort((a, b) => a.y - b.y);
  for (const it of sorted) drawItem(ctx, it, cam);

  // players sorted by y with local player
  const all = [...Object.values(others), me].sort((a, b) => a.y - b.y);
  for (const p of all) drawPlayer(ctx, p, cam, p.id === me.id, t, emotes[p.id]);
}

function drawIsland(ctx, canvas, cam) {
  const W = canvas.width, H = canvas.height;
  ctx.fillStyle = "#7BC676";
  ctx.fillRect(0, 0, W, H);

  const tile = 80;
  const startX = Math.floor(cam.x / tile) * tile;
  const startY = Math.floor(cam.y / tile) * tile;
  for (let gx = startX; gx < cam.x + W + tile; gx += tile) {
    for (let gy = startY; gy < cam.y + H + tile; gy += tile) {
      if (((gx / tile) + (gy / tile)) % 2 === 0) {
        ctx.fillStyle = "rgba(255,255,255,0.05)";
        ctx.fillRect(gx - cam.x, gy - cam.y, tile, tile);
      }
    }
  }

  ctx.strokeStyle = "#F4E2B8";
  ctx.lineWidth = 26;
  ctx.strokeRect(13 - cam.x, 13 - cam.y, WORLD.w - 26, WORLD.h - 26);

  drawPond(ctx, 650 - cam.x, 520 - cam.y, 150, 100);
  drawPond(ctx, 1450 - cam.x, 1000 - cam.y, 120, 90);

  ctx.strokeStyle = "#D9C29A";
  ctx.lineWidth = 46;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(300 - cam.x, 300 - cam.y);
  ctx.quadraticCurveTo(1000 - cam.x, 750 - cam.y, 1700 - cam.x, 1200 - cam.y);
  ctx.stroke();
}

function drawInterior(ctx, canvas, cam) {
  const W = canvas.width, H = canvas.height;
  // wallpaper
  ctx.fillStyle = "#F3D9B5";
  ctx.fillRect(0, 0, W, H);
  const floorTop = 130 - cam.y;
  // wall pattern
  ctx.fillStyle = "rgba(255,255,255,0.25)";
  for (let wx = 0; wx < HOUSE_WORLD.w; wx += 60) {
    ctx.fillRect(wx - cam.x + 20, 0 - cam.y, 4, 130);
  }
  // floor
  ctx.fillStyle = "#C8955B";
  ctx.fillRect(0 - cam.x, floorTop, HOUSE_WORLD.w, HOUSE_WORLD.h - 130);
  ctx.strokeStyle = "rgba(92,64,51,0.2)";
  ctx.lineWidth = 2;
  for (let py = 130; py < HOUSE_WORLD.h; py += 46) {
    const yy = py - cam.y;
    ctx.beginPath(); ctx.moveTo(0 - cam.x, yy); ctx.lineTo(HOUSE_WORLD.w - cam.x, yy); ctx.stroke();
  }
  // baseboard
  ctx.fillStyle = "#A9744F";
  ctx.fillRect(0 - cam.x, floorTop - 10, HOUSE_WORLD.w, 10);
  // room outline
  ctx.strokeStyle = "#5C4033";
  ctx.lineWidth = 10;
  ctx.strokeRect(5 - cam.x, 5 - cam.y, HOUSE_WORLD.w - 10, HOUSE_WORLD.h - 10);
  // exit mat
  const dx = HOUSE_WORLD.w / 2 - cam.x;
  const dyy = HOUSE_WORLD.h - 34 - cam.y;
  ctx.fillStyle = "#8B5A2B";
  ctx.beginPath(); ctx.roundRect(dx - 44, dyy - 20, 88, 44, 8); ctx.fill();
  ctx.strokeStyle = "#5C4033"; ctx.lineWidth = 3; ctx.stroke();
  ctx.fillStyle = "#FFE67D"; ctx.font = "bold 13px Fredoka, sans-serif";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText("↓ EXIT", dx, dyy + 2);
}

function drawHouse(ctx, h, cam, myId) {
  const x = h.x - cam.x, y = h.y - cam.y;
  const mine = h.owner_id === myId;
  ctx.save();
  // shadow
  ctx.beginPath(); ctx.ellipse(x, y + 6, 70, 16, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(0,0,0,0.12)"; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = "#5C4033";
  // body
  ctx.fillStyle = "#FFF3DF";
  ctx.beginPath(); ctx.roundRect(x - 58, y - 78, 116, 84, 8); ctx.fill(); ctx.stroke();
  // roof
  ctx.beginPath();
  ctx.moveTo(x - 70, y - 72); ctx.lineTo(x, y - 126); ctx.lineTo(x + 70, y - 72); ctx.closePath();
  ctx.fillStyle = mine ? (h.color || "#FF9AA2") : "#E07A5F"; ctx.fill(); ctx.stroke();
  // door
  ctx.fillStyle = "#8B5A2B";
  ctx.beginPath(); ctx.roundRect(x - 16, y - 46, 32, 52, 4); ctx.fill(); ctx.stroke();
  ctx.fillStyle = "#FFE67D";
  ctx.beginPath(); ctx.arc(x + 9, y - 20, 2.5, 0, Math.PI * 2); ctx.fill();
  // windows
  ctx.fillStyle = "#AEE3F5";
  [[-38, -50], [38, -50]].forEach(([a, b]) => {
    ctx.beginPath(); ctx.roundRect(x + a - 11, y + b, 22, 22, 3); ctx.fill(); ctx.stroke();
  });
  // nameplate
  ctx.font = "bold 13px Fredoka, sans-serif";
  const label = `${h.owner_name}'s House`;
  const w = ctx.measureText(label).width + 18;
  ctx.fillStyle = mine ? "#FFE67D" : "#FFFBF4";
  ctx.beginPath(); ctx.roundRect(x - w / 2, y - 150, w, 22, 11); ctx.fill(); ctx.stroke();
  ctx.fillStyle = "#3D271D"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(label, x, y - 139);
  ctx.restore();
}

function drawPond(ctx, x, y, rx, ry) {
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(x, y, rx + 8, ry + 8, 0, 0, Math.PI * 2);
  ctx.fillStyle = "#C7E89A";
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = "#6FC3E0";
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(x - rx * 0.3, y - ry * 0.3, rx * 0.4, ry * 0.3, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255,255,255,0.3)";
  ctx.fill();
  ctx.restore();
}

function drawItem(ctx, it, cam) {
  const x = it.x - cam.x, y = it.y - cam.y;
  const meta = ITEM_BY_ID[it.type];
  const color = meta?.color || "#C89B6E";
  ctx.save();
  // shadow
  ctx.beginPath();
  ctx.ellipse(x, y + 16, 20, 7, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(0,0,0,0.12)";
  ctx.fill();
  ctx.translate(x, y);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#5C4033";

  const rr = (rx, ry, w, h, r) => {
    ctx.beginPath();
    ctx.roundRect(rx, ry, w, h, r);
  };

  switch (it.type) {
    case "tree":
      ctx.fillStyle = "#8B5A2B"; rr(-6, -4, 12, 24, 3); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.arc(0, -22, 24, 0, Math.PI * 2); ctx.fillStyle = "#4CAF50"; ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#FF6B6B";
      [[-10, -28], [10, -20], [0, -34]].forEach(([a, b]) => { ctx.beginPath(); ctx.arc(a, b, 4, 0, Math.PI * 2); ctx.fill(); });
      break;
    case "flower":
      ctx.fillStyle = "#C97B4A"; rr(-9, 6, 18, 14, 3); ctx.fill(); ctx.stroke();
      ctx.fillStyle = color;
      [[-7, -6], [7, -6], [-7, 4], [7, 4], [0, -1]].forEach(([a, b], i) => {
        ctx.beginPath(); ctx.arc(a, b - 6, i === 4 ? 5 : 6, 0, Math.PI * 2); ctx.fillStyle = i === 4 ? "#FFE67D" : color; ctx.fill();
      });
      break;
    case "lamp":
      ctx.fillStyle = "#6B5A4A"; rr(-3, -2, 6, 26, 2); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(-12, -4); ctx.lineTo(12, -4); ctx.lineTo(8, -22); ctx.lineTo(-8, -22); ctx.closePath();
      ctx.fillStyle = color; ctx.fill(); ctx.stroke();
      break;
    case "chair":
      ctx.fillStyle = color; rr(-12, 0, 24, 8, 3); ctx.fill(); ctx.stroke();
      rr(-12, -20, 6, 22, 3); ctx.fill(); ctx.stroke();
      break;
    case "table":
      ctx.fillStyle = color; rr(-18, -6, 36, 10, 4); ctx.fill(); ctx.stroke();
      rr(-15, 2, 5, 16, 2); ctx.fill(); ctx.stroke(); rr(10, 2, 5, 16, 2); ctx.fill(); ctx.stroke();
      break;
    case "fence":
      ctx.fillStyle = color;
      rr(-18, -14, 6, 30, 2); ctx.fill(); ctx.stroke(); rr(12, -14, 6, 30, 2); ctx.fill(); ctx.stroke();
      rr(-18, -8, 36, 5, 2); ctx.fill(); ctx.stroke(); rr(-18, 4, 36, 5, 2); ctx.fill(); ctx.stroke();
      break;
    case "blanket":
      ctx.fillStyle = color; rr(-20, -14, 40, 30, 5); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      for (let a = -20; a < 20; a += 10) for (let b = -14; b < 16; b += 10) { if (((a + b) / 10) % 2 === 0) ctx.fillRect(a, b, 10, 10); }
      ctx.strokeRect(-20, -14, 40, 30);
      break;
    case "bench":
      ctx.fillStyle = color; rr(-18, -2, 36, 8, 3); ctx.fill(); ctx.stroke();
      rr(-18, -16, 36, 6, 3); ctx.fill(); ctx.stroke();
      rr(-16, 6, 5, 12, 2); ctx.fill(); ctx.stroke(); rr(11, 6, 5, 12, 2); ctx.fill(); ctx.stroke();
      break;
    default:
      ctx.fillStyle = color; ctx.beginPath(); ctx.arc(0, 0, 14, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }
  ctx.restore();
}

function drawPlayer(ctx, p, cam, isMe, t, emote) {
  const bob = p.moving ? Math.sin(t / 90) * 2 : 0;
  const x = p.x - cam.x, y = p.y - cam.y + bob;
  ctx.save();
  // shadow
  ctx.beginPath();
  ctx.ellipse(x, p.y - cam.y + 20, 16, 6, 0, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(0,0,0,0.15)";
  ctx.fill();

  // body
  ctx.beginPath();
  ctx.arc(x, y, PLAYER_R, 0, Math.PI * 2);
  ctx.fillStyle = p.color || "#FF9AA2";
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = p.border || "#5C4033";
  ctx.stroke();

  // face direction eyes
  const dir = p.dir || "down";
  let ex = 0, ey = 2;
  if (dir === "left") ex = -5; else if (dir === "right") ex = 5;
  else if (dir === "up") ey = -4; else ey = 4;
  ctx.fillStyle = "#3D271D";
  if (dir !== "up") {
    ctx.beginPath(); ctx.arc(x - 6 + ex * 0.4, y + ey, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x + 6 + ex * 0.4, y + ey, 2.6, 0, Math.PI * 2); ctx.fill();
    // cheeks
    ctx.fillStyle = "rgba(255,120,120,0.4)";
    ctx.beginPath(); ctx.arc(x - 9, y + ey + 3, 3, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x + 9, y + ey + 3, 3, 0, Math.PI * 2); ctx.fill();
  }

  // name tag
  ctx.font = "bold 13px Fredoka, sans-serif";
  const label = p.name || "Villager";
  const w = ctx.measureText(label).width + 16;
  ctx.fillStyle = isMe ? "#FFE67D" : "#FFFBF4";
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - PLAYER_R - 24, w, 20, 10);
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#5C4033";
  ctx.stroke();
  ctx.fillStyle = "#3D271D";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, x, y - PLAYER_R - 13);

  // floating emote
  if (emote && emote.until > t) {
    const age = (emote.until - t) / 2200; // 1 -> 0
    const pop = age > 0.85 ? (1 - age) / 0.15 : 1;
    const ey2 = y - PLAYER_R - 40 - (1 - age) * 14;
    ctx.save();
    ctx.globalAlpha = Math.min(1, age * 3);
    ctx.font = `${Math.round(30 * pop)}px sans-serif`;
    ctx.fillText(emote.emote, x, ey2);
    ctx.restore();
  }
  ctx.restore();
}
