import "@/App.css";
import { useState } from "react";
import Lobby from "@/game/Lobby";
import IslandGame from "@/game/IslandGame";
import { Toaster } from "@/components/ui/sonner";

function App() {
  const [session, setSession] = useState(null); // { code, player }

  return (
    <div className="App">
      {session ? (
        <IslandGame
          code={session.code}
          player={session.player}
          onLeave={() => setSession(null)}
        />
      ) : (
        <Lobby onEnter={(code, player) => setSession({ code, player })} />
      )}
      <Toaster position="top-center" />
    </div>
  );
}

export default App;
