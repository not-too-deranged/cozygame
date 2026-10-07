"""
Backend tests for iteration 4: Bells wallet, shop, farming (plant/harvest/sell/buy).
Covers wallet init & persistence, buy_seed, plant, harvest (ripeness gate),
sell_crop, buy_furniture (overspend & already-owned rejection), crop zone
isolation, reconnect persistence of planted crops, wallet messages scoping.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
import websockets
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
WS_BASE = BASE_URL.replace("http", "ws", 1)

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_Econ"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["code"]


async def _recv_until(ws, mtype, timeout=4.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        remaining = max(0.1, end - asyncio.get_event_loop().time())
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return None
        msg = json.loads(raw)
        if msg.get("type") == mtype:
            return msg
    return None


async def _drain(ws, duration=0.4):
    out = []
    end = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
            out.append(json.loads(raw))
        except asyncio.TimeoutError:
            continue
        except Exception:
            break
    return out


async def _join(ws, name="Tester", pid=None):
    pid = pid or str(uuid.uuid4())
    await ws.send(json.dumps({
        "type": "join",
        "player": {"id": pid, "name": name, "color": "#FF9AA2", "border": "#E06873"},
    }))
    init = await _recv_until(ws, "init", timeout=5)
    assert init is not None, "did not receive init"
    return pid, init


# ---------------- Tests ----------------

@pytest.mark.asyncio
async def test_init_has_wallet_and_crops_arrays():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Alice")
        assert "wallet" in init, "init missing wallet"
        w = init["wallet"]
        assert w["bells"] == 120
        assert w["seeds"] == {}
        assert w["crops"] == {}
        # Iteration 6: starter furniture kit (replaces old 'unlocked' array)
        assert "furniture" in w and isinstance(w["furniture"], dict)
        assert w["furniture"].get("chair") == 5
        assert w["furniture"].get("flower") == 6
        assert "crops" in init and isinstance(init["crops"], list) and init["crops"] == []


@pytest.mark.asyncio
async def test_buy_seed_deducts_bells_and_rejects_overspend():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Alice")
        # Buy 2 tomato seeds (cost 10 each) -> 120 -> 100
        await ws.send(json.dumps({"type": "buy_seed", "cropType": "tomato"}))
        w1 = await _recv_until(ws, "wallet", 3)
        assert w1 and w1["bells"] == 110 and w1["seeds"].get("tomato") == 1
        await ws.send(json.dumps({"type": "buy_seed", "cropType": "tomato"}))
        w2 = await _recv_until(ws, "wallet", 3)
        assert w2 and w2["bells"] == 100 and w2["seeds"].get("tomato") == 2

        # Overspend: buy pumpkin (22) 5 times -> after 4 buys bells=12 < 22 -> 5th rejected
        for _ in range(4):
            await ws.send(json.dumps({"type": "buy_seed", "cropType": "pumpkin"}))
            await _recv_until(ws, "wallet", 3)
        # Current bells 100 - 4*22 = 12. Next pumpkin buy MUST be rejected (no wallet msg)
        await ws.send(json.dumps({"type": "buy_seed", "cropType": "pumpkin"}))
        rej = await _recv_until(ws, "wallet", 1.5)
        assert rej is None, f"overspend not rejected: got {rej}"


@pytest.mark.asyncio
async def test_plant_consumes_seed_and_zone_isolated_and_persists():
    code = _create_room()
    pid = str(uuid.uuid4())
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        await _join(ws, "Alice", pid=pid)
        # Plant without seed -> no-op
        await ws.send(json.dumps({"type": "plant", "cropType": "carrot", "x": 1000, "y": 800}))
        assert await _recv_until(ws, "plant_crop", 1.0) is None

        # Buy carrot
        await ws.send(json.dumps({"type": "buy_seed", "cropType": "carrot"}))
        await _recv_until(ws, "wallet", 3)
        # Plant
        await ws.send(json.dumps({"type": "plant", "cropType": "carrot", "x": 1000, "y": 800}))
        pc = await _recv_until(ws, "plant_crop", 3)
        assert pc and pc["crop"]["type"] == "carrot"
        wal = await _recv_until(ws, "wallet", 3)
        assert wal and "carrot" not in wal["seeds"], "seed not consumed to zero"

        # Build house, enter -> zone_state crops must be empty
        await ws.send(json.dumps({"type": "build_house"}))
        await _recv_until(ws, "house", 3)
        await ws.send(json.dumps({"type": "enter_zone", "zone": f"house:{pid}"}))
        zs = await _recv_until(ws, "zone_state", 3)
        assert zs and zs["crops"] == [], "house zone must have no crops"

        # Back to island -> zone_state.crops includes the planted one
        await ws.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs2 = await _recv_until(ws, "zone_state", 3)
        assert zs2 and any(c["type"] == "carrot" for c in zs2["crops"]), "crop missing on island zone"

    # Reconnect fresh WS -> init.crops includes carrot
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws2:
        _, init = await _join(ws2, "Bob")
        assert any(c["type"] == "carrot" for c in init["crops"]), "crop not persisted across reconnect"


@pytest.mark.asyncio
async def test_harvest_ripeness_gate_and_credit():
    code = _create_room()
    pid = str(uuid.uuid4())
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        await _join(ws, "Farmer", pid=pid)
        # Buy & plant tomato
        await ws.send(json.dumps({"type": "buy_seed", "cropType": "tomato"}))
        await _recv_until(ws, "wallet", 3)
        await ws.send(json.dumps({"type": "plant", "cropType": "tomato", "x": 950, "y": 780}))
        pc = await _recv_until(ws, "plant_crop", 3)
        await _recv_until(ws, "wallet", 2)
        crop_id = pc["crop"]["id"]

        # Harvest unripe -> no-op
        await ws.send(json.dumps({"type": "harvest", "cropId": crop_id}))
        assert await _recv_until(ws, "harvest", 1.5) is None, "unripe crop was harvested!"

        # Backdate crop's planted_at to force ripeness via direct Mongo write
        mc = AsyncIOMotorClient(MONGO_URL)
        db = mc[DB_NAME]
        old_iso = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        upd = await db.crops.update_one({"code": code, "id": crop_id}, {"$set": {"planted_at": old_iso}})
        assert upd.modified_count == 1
        mc.close()

        # Harvest now -> succeeds
        await ws.send(json.dumps({"type": "harvest", "cropId": crop_id}))
        h = await _recv_until(ws, "harvest", 3)
        assert h and h["cropId"] == crop_id
        wal = await _recv_until(ws, "wallet", 3)
        assert wal and wal["crops"].get("tomato") == 1


@pytest.mark.asyncio
async def test_sell_crop_requires_held_and_credits_bells():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Seller")
        start = init["wallet"]["bells"]
        # Sell with none -> no-op
        await ws.send(json.dumps({"type": "sell_crop", "cropType": "carrot"}))
        assert await _recv_until(ws, "wallet", 1.5) is None

        # Seed held crops directly via Mongo to isolate sell logic
        mc = AsyncIOMotorClient(MONGO_URL)
        db = mc[DB_NAME]
        # Find player_state doc (name was Seller)
        state = await db.player_state.find_one({"code": code})
        pid = state["player_id"]
        await db.player_state.update_one({"code": code, "player_id": pid},
                                         {"$set": {"crops": {"strawberry": 2}}})
        mc.close()

        await ws.send(json.dumps({"type": "sell_crop", "cropType": "strawberry"}))
        w = await _recv_until(ws, "wallet", 3)
        assert w and w["bells"] == start + 38 and w["crops"].get("strawberry") == 1
        await ws.send(json.dumps({"type": "sell_crop", "cropType": "strawberry"}))
        w2 = await _recv_until(ws, "wallet", 3)
        assert w2 and w2["bells"] == start + 76 and "strawberry" not in w2["crops"]
        # Third sell -> no-op
        await ws.send(json.dumps({"type": "sell_crop", "cropType": "strawberry"}))
        assert await _recv_until(ws, "wallet", 1.2) is None


@pytest.mark.asyncio
async def test_buy_furniture_rejects_overspend_and_is_repeatable_and_placeable():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Shopper")
        assert init["wallet"]["bells"] == 120
        # Cannot afford fountain (140)
        await ws.send(json.dumps({"type": "buy_furniture", "itemId": "fountain"}))
        assert await _recv_until(ws, "wallet", 1.2) is None, "fountain purchase should fail"

        # Buy lamppost (70) -> ok, count becomes 1
        await ws.send(json.dumps({"type": "buy_furniture", "itemId": "lamppost"}))
        w = await _recv_until(ws, "wallet", 3)
        assert w and w["bells"] == 50 and w["furniture"].get("lamppost") == 1

        # Iteration 6: buy_furniture is now repeatable (stacks the count)
        # But player can't afford another lamppost (50 bells < 70). Verify no wallet msg.
        await ws.send(json.dumps({"type": "buy_furniture", "itemId": "lamppost"}))
        assert await _recv_until(ws, "wallet", 1.2) is None, "unaffordable repeat buy should be rejected"

        # Place a lamppost on island -> count decrements to 0 (removed from dict)
        await ws.send(json.dumps({"type": "place", "itemType": "lamppost", "x": 1100, "y": 800}))
        pl = await _recv_until(ws, "place", 3)
        assert pl and pl["item"]["type"] == "lamppost"
        wal = await _recv_until(ws, "wallet", 3)
        assert wal and "lamppost" not in wal["furniture"], "lamppost should be removed from furniture dict at 0"


@pytest.mark.asyncio
async def test_wallet_messages_scoped_to_actor_only():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        await _join(a, "Alice")
        await _join(b, "Bob")
        await _drain(a, 0.3); await _drain(b, 0.3)
        await a.send(json.dumps({"type": "buy_seed", "cropType": "tomato"}))
        wa = await _recv_until(a, "wallet", 3)
        assert wa and wa["bells"] == 110
        # Bob should NOT receive a wallet message
        msgs = await _drain(b, 1.0)
        assert not any(m.get("type") == "wallet" for m in msgs), "wallet leaked to other player"
