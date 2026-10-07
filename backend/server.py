from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import string
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

SPAWN = {"x": 1000, "y": 750}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def gen_code():
    return ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=5))


# ---------- Models ----------
class CreateRoomReq(BaseModel):
    name: str = Field(default="Cozy Island")


class PlacedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    x: float
    y: float
    rotation: int = 0
    placed_by: str = ""


# ---------- REST ----------
@api_router.get("/")
async def root():
    return {"message": "Cozy Island API"}


@api_router.post("/rooms/create")
async def create_room(req: CreateRoomReq):
    code = gen_code()
    while await db.rooms.find_one({"code": code}):
        code = gen_code()
    doc = {"code": code, "name": req.name, "created_at": now_iso()}
    await db.rooms.insert_one(doc)
    return {"code": code, "name": req.name}


@api_router.get("/rooms/{code}")
async def get_room(code: str):
    code = code.upper()
    room = await db.rooms.find_one({"code": code}, {"_id": 0})
    if not room:
        raise HTTPException(status_code=404, detail="Island not found. Check the code!")
    items = await db.items.find({"code": code}, {"_id": 0}).to_list(2000)
    chat = await db.chat.find({"code": code}, {"_id": 0}).sort("ts", -1).to_list(50)
    chat.reverse()
    return {"room": room, "items": items, "chat": chat}


# ---------- WebSocket real-time ----------
class RoomHub:
    def __init__(self):
        # code -> { player_id: {"ws": ws, "player": {...}} }
        self.rooms: Dict[str, Dict[str, dict]] = {}

    def players_public(self, code):
        return [c["player"] for c in self.rooms.get(code, {}).values()]

    async def broadcast(self, code, message, exclude=None):
        for pid, conn in list(self.rooms.get(code, {}).items()):
            if pid == exclude:
                continue
            try:
                await conn["ws"].send_json(message)
            except Exception:
                pass


hub = RoomHub()


@app.websocket("/api/ws/{code}")
async def ws_endpoint(websocket: WebSocket, code: str):
    code = code.upper()
    await websocket.accept()
    player_id = None
    try:
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")

            if mtype == "join":
                p = data.get("player", {})
                player_id = p.get("id") or str(uuid.uuid4())
                player = {
                    "id": player_id,
                    "name": p.get("name", "Villager")[:16],
                    "color": p.get("color", "#FF9AA2"),
                    "border": p.get("border", "#E06873"),
                    "x": SPAWN["x"],
                    "y": SPAWN["y"],
                    "dir": "down",
                }
                self_room = self_ensure(code)
                self_room[player_id] = {"ws": websocket, "player": player}
                # send init state to joiner
                items = await db.items.find({"code": code}, {"_id": 0}).to_list(2000)
                chat = await db.chat.find({"code": code}, {"_id": 0}).sort("ts", -1).to_list(50)
                chat.reverse()
                await websocket.send_json({
                    "type": "init",
                    "you": player,
                    "players": hub.players_public(code),
                    "items": items,
                    "chat": chat,
                })
                await hub.broadcast(code, {"type": "player_join", "player": player}, exclude=player_id)
                await hub.broadcast(code, {"type": "players", "players": hub.players_public(code)})

            elif mtype == "move" and player_id:
                conn = hub.rooms.get(code, {}).get(player_id)
                if conn:
                    conn["player"]["x"] = data.get("x", conn["player"]["x"])
                    conn["player"]["y"] = data.get("y", conn["player"]["y"])
                    conn["player"]["dir"] = data.get("dir", conn["player"]["dir"])
                    await hub.broadcast(code, {
                        "type": "move",
                        "id": player_id,
                        "x": conn["player"]["x"],
                        "y": conn["player"]["y"],
                        "dir": conn["player"]["dir"],
                    }, exclude=player_id)

            elif mtype == "chat" and player_id:
                conn = hub.rooms.get(code, {}).get(player_id)
                text = (data.get("text") or "").strip()[:200]
                if conn and text:
                    msg = {
                        "code": code,
                        "player": conn["player"]["name"],
                        "color": conn["player"]["color"],
                        "text": text,
                        "ts": now_iso(),
                    }
                    await db.chat.insert_one(dict(msg))
                    msg.pop("_id", None)
                    await hub.broadcast(code, {"type": "chat", "message": {k: v for k, v in msg.items() if k != "code"}})

            elif mtype == "place" and player_id:
                item = PlacedItem(
                    type=data.get("itemType", "flower"),
                    x=float(data.get("x", SPAWN["x"])),
                    y=float(data.get("y", SPAWN["y"])),
                    rotation=int(data.get("rotation", 0)),
                    placed_by=player_id,
                )
                doc = item.model_dump()
                doc["code"] = code
                await db.items.insert_one(dict(doc))
                doc.pop("_id", None)
                public = {k: v for k, v in doc.items() if k != "code"}
                await hub.broadcast(code, {"type": "place", "item": public})

            elif mtype == "pickup" and player_id:
                item_id = data.get("itemId")
                if item_id:
                    await db.items.delete_one({"code": code, "id": item_id})
                    await hub.broadcast(code, {"type": "pickup", "itemId": item_id})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.getLogger(__name__).warning(f"ws error: {e}")
    finally:
        if player_id and code in hub.rooms and player_id in hub.rooms[code]:
            del hub.rooms[code][player_id]
            await hub.broadcast(code, {"type": "player_leave", "id": player_id})
            await hub.broadcast(code, {"type": "players", "players": hub.players_public(code)})
            if not hub.rooms[code]:
                del hub.rooms[code]


def self_ensure(code):
    if code not in hub.rooms:
        hub.rooms[code] = {}
    return hub.rooms[code]


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
