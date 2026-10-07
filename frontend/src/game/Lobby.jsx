import { useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Palmtree, Users, Plus, LogIn, Loader2 } from "lucide-react";
import { AVATAR_COLORS } from "@/game/items";
import { sfx } from "@/game/sound";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Lobby({ onEnter }) {
  const [tab, setTab] = useState("create");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [colorIdx, setColorIdx] = useState(0);
  const [loading, setLoading] = useState(false);

  const color = AVATAR_COLORS[colorIdx];

  const makePlayer = () => ({
    id: crypto.randomUUID(),
    name: name.trim() || "Villager",
    color: color.hex,
    border: color.border,
  });

  const handleCreate = async () => {
    if (!name.trim()) return toast.error("Pick a villager name first!");
    setLoading(true);
    try {
      const res = await axios.post(`${API}/rooms/create`, { name: `${name.trim()}'s Island` });
      sfx.join();
      onEnter(res.data.code, makePlayer());
    } catch {
      toast.error("Could not create island. Try again!");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    if (!name.trim()) return toast.error("Pick a villager name first!");
    if (code.trim().length < 4) return toast.error("Enter a valid room code!");
    setLoading(true);
    try {
      await axios.get(`${API}/rooms/${code.trim().toUpperCase()}`);
      sfx.join();
      onEnter(code.trim().toUpperCase(), makePlayer());
    } catch {
      toast.error("Island not found. Check the code!");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="w-screen min-h-screen overflow-auto flex items-center justify-center p-4 font-['Nunito'] relative"
      style={{
        background:
          "radial-gradient(circle at 20% 20%, #A8E063 0%, #7BC676 40%, #56A65B 100%)",
      }}
    >
      {/* floating decorations */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {["🌸", "🍃", "🌼", "🐚", "🌿", "🍀"].map((e, i) => (
          <div
            key={i}
            className="absolute text-3xl opacity-40 animate-float-bob"
            style={{
              left: `${[8, 82, 15, 88, 45, 70][i]}%`,
              top: `${[18, 25, 70, 68, 12, 80][i]}%`,
              animationDelay: `${i * 0.5}s`,
            }}
          >
            {e}
          </div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 22 }}
        className="max-w-md w-full p-7 sm:p-8 bg-[#FFFBF4] border-4 border-[#5C4033] rounded-[32px] shadow-[0_12px_0_rgba(92,64,51,0.2)] text-center relative z-10"
        data-testid="lobby-card"
      >
        <div className="flex items-center justify-center gap-2 mb-1">
          <Palmtree className="w-8 h-8 text-[#4CAF50]" strokeWidth={2.5} />
          <h1 className="text-3xl sm:text-4xl font-bold text-[#4A3525] font-['Fredoka'] tracking-tight">
            Cozy Island
          </h1>
        </div>
        <p className="text-[#7C5A3E] font-semibold mb-6 text-sm">
          Hang out with friends on a shared island 🏝️
        </p>

        {/* Name */}
        <label className="block text-left text-xs font-bold uppercase tracking-wider text-[#7C5A3E] mb-1.5">
          Villager Name
        </label>
        <input
          data-testid="player-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={16}
          placeholder="e.g. Tom"
          className="w-full bg-[#FAF0E4] border-[3px] border-[#5C4033] text-[#3D271D] rounded-2xl p-3.5 text-center font-bold font-['Fredoka'] placeholder-[#A0836C] focus:ring-4 focus:ring-[#9ED89D] outline-none mb-5"
        />

        {/* Avatar colors */}
        <label className="block text-left text-xs font-bold uppercase tracking-wider text-[#7C5A3E] mb-2">
          Choose Your Look
        </label>
        <div className="grid grid-cols-6 gap-2 mb-6">
          {AVATAR_COLORS.map((c, i) => (
            <button
              key={c.name}
              data-testid={`avatar-color-${i}`}
              onClick={() => { setColorIdx(i); sfx.click(); }}
              className={`aspect-square rounded-full border-[3px] transition-all ${
                colorIdx === i ? "scale-110 ring-4 ring-[#5C4033]/30 -translate-y-0.5" : "hover:scale-105"
              }`}
              style={{ background: c.hex, borderColor: c.border }}
              title={c.name}
            />
          ))}
        </div>

        {/* Tabs */}
        <div className="flex bg-[#FAF0E4] rounded-full p-1 border-[3px] border-[#5C4033] mb-5">
          {[
            { id: "create", label: "Create", icon: Plus },
            { id: "join", label: "Join", icon: LogIn },
          ].map((t) => (
            <button
              key={t.id}
              data-testid={`tab-${t.id}`}
              onClick={() => { setTab(t.id); sfx.click(); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-full font-['Fredoka'] font-bold transition-all ${
                tab === t.id
                  ? "bg-[#FFFBF4] text-[#5C4033] shadow-[0_3px_0_#C9A77F]"
                  : "text-[#A0836C]"
              }`}
            >
              <t.icon className="w-4 h-4" /> {t.label}
            </button>
          ))}
        </div>

        {tab === "join" && (
          <input
            data-testid="room-code-input"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            maxLength={5}
            placeholder="ROOM CODE"
            className="w-full uppercase tracking-[0.3em] bg-[#FAF0E4] border-[3px] border-[#5C4033] text-[#3D271D] rounded-2xl p-3.5 text-center font-extrabold text-xl font-['Fredoka'] placeholder-[#C9A77F] focus:ring-4 focus:ring-[#8ECEF1] outline-none mb-5"
          />
        )}

        <button
          data-testid={tab === "create" ? "create-room-button" : "join-room-button"}
          onClick={tab === "create" ? handleCreate : handleJoin}
          disabled={loading}
          className="w-full py-3.5 bg-[#9ED89D] text-[#2D5A27] font-extrabold text-lg font-['Fredoka'] rounded-2xl border-[3px] border-[#3A8037] shadow-[0_6px_0_#3A8037] hover:bg-[#B0E8AF] hover:-translate-y-0.5 active:translate-y-1 active:shadow-[0_1px_0_#3A8037] transition-all flex items-center justify-center gap-2 disabled:opacity-70"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              {tab === "create" ? <Users className="w-5 h-5" /> : <LogIn className="w-5 h-5" />}
              {tab === "create" ? "Create My Island" : "Join Island"}
            </>
          )}
        </button>
      </motion.div>
    </div>
  );
}
