"""
Iteration 6: Finite per-player furniture inventory.
Covers:
- Starter kit on first join and backfill for existing docs
- place decrements furniture + sends wallet; no-op at 0
- pickup refunds +1 to picker
- buy_furniture is repeatable (increments count)
- Furniture persists across reconnect; wallet scoping
"""
import asyncio
import json
import os
import uuid

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

STARTER = {
    "chair": 5, "table": 5, "flower": 6, "lamp": 5, "fence": 8, "tree": 5,
    "blanket": 4, "bench": 4, "bed": 3, "rug": 5, "bookshelf": 4, "plant": 6,
}


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_Furn"}, timeout=15)
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


# ------------- Tests -------------

@pytest.mark.asyncio
async def test_starter_kit_on_new_player():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Newbie")
        fur = init["wallet"]["furniture"]
        for k, v in STARTER.items():
            assert fur.get(k) == v, f"starter kit missing {k}={v}, got {fur.get(k)}"


@pytest.mark.asyncio
async def test_backfill_furniture_for_existing_doc():
    """Insert a player_state WITHOUT furniture; on connect, get_state should backfill."""
    code = _create_room()
    pid = str(uuid.uuid4())
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    await db.player_state.insert_one({
        "code": code, "player_id": pid, "name": "Legacy",
        "bells": 50, "seeds": {}, "crops": {},
    })
    try:
        async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
            _, init = await _join(ws, "Legacy", pid=pid)
            fur = init["wallet"]["furniture"]
            assert fur.get("chair") == 5 and fur.get("flower") == 6
            # Preserve existing bells
            assert init["wallet"]["bells"] == 50
            # Verify DB updated
            doc = await db.player_state.find_one({"code": code, "player_id": pid})
            assert doc.get("furniture", {}).get("chair") == 5
    finally:
        cli.close()


@pytest.mark.asyncio
async def test_place_decrements_and_broadcasts_wallet_to_actor_only():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        _, init_a = await _join(a, "Alice")
        _, _ = await _join(b, "Bob")
        await _drain(a, 0.3); await _drain(b, 0.3)
        await a.send(json.dumps({"type": "place", "itemType": "chair", "x": 1050, "y": 760}))
        pl = await _recv_until(a, "place", 3)
        assert pl and pl["item"]["type"] == "chair"
        wal = await _recv_until(a, "wallet", 3)
        assert wal and wal["furniture"]["chair"] == 4
        # Bob gets the place broadcast but NO wallet
        bob_msgs = await _drain(b, 0.8)
        assert any(m.get("type") == "place" for m in bob_msgs)
        assert not any(m.get("type") == "wallet" for m in bob_msgs), "wallet leaked to other player"


@pytest.mark.asyncio
async def test_place_noop_when_count_zero():
    """Place a type with 0 count: no item, no 'place' broadcast, no decrement."""
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Alice")
        await _drain(ws, 0.3)
        # bed starts at 3 -> place 3 beds to drain
        for i in range(3):
            await ws.send(json.dumps({"type": "place", "itemType": "bed", "x": 1000 + i*20, "y": 760}))
            await _recv_until(ws, "place", 3)
            await _recv_until(ws, "wallet", 3)
        # 4th attempt: NO-OP
        await ws.send(json.dumps({"type": "place", "itemType": "bed", "x": 1100, "y": 760}))
        pl = await _recv_until(ws, "place", 1.2)
        assert pl is None, "no place broadcast expected when count is 0"
        wal = await _recv_until(ws, "wallet", 1.2)
        assert wal is None, "no wallet update expected on no-op"


@pytest.mark.asyncio
async def test_pickup_refunds_furniture_to_picker():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        _, _ = await _join(a, "Alice")
        _, _ = await _join(b, "Bob")
        await _drain(a, 0.3); await _drain(b, 0.3)
        # Alice places chair (5->4)
        await a.send(json.dumps({"type": "place", "itemType": "chair", "x": 1050, "y": 760}))
        pl_a = await _recv_until(a, "place", 3)
        item_id = pl_a["item"]["id"]
        wal_a = await _recv_until(a, "wallet", 3)
        assert wal_a["furniture"]["chair"] == 4
        # Bob picks it up -> Bob should get +1 chair (starter 5 -> 6)
        pl_b = await _recv_until(b, "place", 2)
        assert pl_b and pl_b["item"]["id"] == item_id
        await _drain(b, 0.2)
        await b.send(json.dumps({"type": "pickup", "itemId": item_id}))
        pk = await _recv_until(b, "pickup", 3)
        assert pk and pk["itemId"] == item_id
        wal_b = await _recv_until(b, "wallet", 3)
        assert wal_b and wal_b["furniture"]["chair"] == 6, f"expected chair=6 for Bob after pickup, got {wal_b['furniture'].get('chair')}"
        # Alice should NOT get a wallet from Bob's pickup
        a_msgs = await _drain(a, 0.8)
        assert any(m.get("type") == "pickup" for m in a_msgs)
        assert not any(m.get("type") == "wallet" for m in a_msgs)


@pytest.mark.asyncio
async def test_pickup_refunds_even_for_absent_type():
    """Pickup of a type the picker has 0/absent of should still refund +1."""
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    # Alice buys lamppost and places it; Bob picks it up (Bob has no lamppost)
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        _, _ = await _join(a, "Alice")
        _, _ = await _join(b, "Bob")
        await _drain(a, 0.3); await _drain(b, 0.3)
        await a.send(json.dumps({"type": "buy_furniture", "itemId": "lamppost"}))
        await _recv_until(a, "wallet", 3)
        await a.send(json.dumps({"type": "place", "itemType": "lamppost", "x": 1100, "y": 800}))
        pl = await _recv_until(a, "place", 3)
        await _recv_until(a, "wallet", 3)
        item_id = pl["item"]["id"]
        # Bob picks it up
        await _drain(b, 0.5)
        await b.send(json.dumps({"type": "pickup", "itemId": item_id}))
        await _recv_until(b, "pickup", 3)
        wal_b = await _recv_until(b, "wallet", 3)
        assert wal_b and wal_b["furniture"].get("lamppost") == 1


@pytest.mark.asyncio
async def test_buy_furniture_is_repeatable_and_stacks():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Shopper")
        # Give extra bells by seeding directly? No, use fish? Simpler: lamppost 70, player has 120 -> can buy 1.
        # To test stacking repeatably, we need enough bells. Seed via DB.
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        try:
            # Find player id from init
            pid = init["you"]["id"]
            await db.player_state.update_one({"code": code, "player_id": pid}, {"$set": {"bells": 1000}})
            await _drain(ws, 0.2)
            # Buy lamppost twice
            await ws.send(json.dumps({"type": "buy_furniture", "itemId": "lamppost"}))
            w1 = await _recv_until(ws, "wallet", 3)
            assert w1 and w1["furniture"].get("lamppost") == 1 and w1["bells"] == 930
            await ws.send(json.dumps({"type": "buy_furniture", "itemId": "lamppost"}))
            w2 = await _recv_until(ws, "wallet", 3)
            assert w2 and w2["furniture"].get("lamppost") == 2 and w2["bells"] == 860
            # Buy fountain (140)
            await ws.send(json.dumps({"type": "buy_furniture", "itemId": "fountain"}))
            w3 = await _recv_until(ws, "wallet", 3)
            assert w3 and w3["furniture"].get("fountain") == 1 and w3["bells"] == 720
        finally:
            cli.close()


@pytest.mark.asyncio
async def test_furniture_persists_across_reconnect():
    code = _create_room()
    pid = str(uuid.uuid4())
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, _ = await _join(ws, "Alice", pid=pid)
        await _drain(ws, 0.3)
        await ws.send(json.dumps({"type": "place", "itemType": "chair", "x": 1050, "y": 760}))
        await _recv_until(ws, "place", 3)
        wal = await _recv_until(ws, "wallet", 3)
        assert wal["furniture"]["chair"] == 4
    # Reconnect with same player id
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws2:
        _, init2 = await _join(ws2, "Alice", pid=pid)
        assert init2["wallet"]["furniture"]["chair"] == 4
