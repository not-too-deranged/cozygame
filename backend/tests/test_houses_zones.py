"""
Backend tests for Cozy Island house/zones features.
Covers:
- build_house (idempotency, persistence, broadcast)
- enter_zone (island / house:<ownerId>, zone_state payload)
- Zone-scoped item isolation
- Zone-scoped presence & movement
- Persistence across reconnect
"""
import asyncio
import json
import os
import uuid
import pytest
import requests
import websockets

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Fallback: read frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

WS_BASE = BASE_URL.replace("http", "ws", 1)


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_House"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["code"]


async def _recv_until(ws, mtype, timeout=5.0, collect_others=False):
    """Receive messages until one of type mtype arrives. Returns (matched, others)."""
    others = []
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        remaining = max(0.1, end - asyncio.get_event_loop().time())
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        msg = json.loads(raw)
        if msg.get("type") == mtype:
            return msg, others
        others.append(msg)
    return None, others


async def _drain(ws, duration=0.6):
    """Drain any pending messages from socket for a short period."""
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


async def _join(ws, name="Tester"):
    pid = str(uuid.uuid4())
    await ws.send(json.dumps({
        "type": "join",
        "player": {"id": pid, "name": name, "color": "#FF9AA2", "border": "#E06873"},
    }))
    init, _ = await _recv_until(ws, "init", timeout=5)
    assert init is not None, "did not receive init"
    return pid, init


# ---- Tests ----

@pytest.mark.asyncio
async def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=10)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_build_house_idempotent_and_broadcast():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, a_init = await _join(a, "Alice")
        b_id, b_init = await _join(b, "Bob")
        # Drain Alice's player_join/players events caused by Bob
        await _drain(a, 0.4)
        # Alice builds house
        await a.send(json.dumps({"type": "build_house"}))
        # Both A and B are on island -> both should receive house broadcast
        a_house, _ = await _recv_until(a, "house", timeout=4)
        b_house, _ = await _recv_until(b, "house", timeout=4)
        assert a_house and b_house, "house broadcast missing"
        assert a_house["house"]["owner_id"] == a_id
        assert a_house["house"]["owner_name"] == "Alice"
        # Second build -> no new house broadcast
        await a.send(json.dumps({"type": "build_house"}))
        dup, _ = await _recv_until(a, "house", timeout=1.5)
        assert dup is None, "duplicate house broadcast - idempotency violated"

        # Verify only 1 doc via REST (GET room has items only; use enter_zone to re-check via houses)
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs is not None
        owners = [h["owner_id"] for h in zs.get("houses", [])]
        assert owners.count(a_id) == 1, f"expected 1 house per owner, got {owners}"


@pytest.mark.asyncio
async def test_enter_zone_payloads_and_item_isolation():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        # Build and enter house
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs is not None
        assert zs["zone"] == f"house:{a_id}"
        assert zs["you"]["x"] == 450 and zs["you"]["y"] == 480
        assert isinstance(zs["players"], list)
        assert len(zs["items"]) == 0

        # Place item inside house
        await a.send(json.dumps({"type": "place", "itemType": "chair", "x": 400, "y": 400}))
        placed, _ = await _recv_until(a, "place", timeout=3)
        assert placed and placed["item"]["type"] == "chair"

        # Go to island -> zone_state items should NOT include chair
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs_isl, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs_isl["zone"] == "island"
        assert all(it["type"] != "chair" or it["x"] != 400 for it in zs_isl["items"]), "house item leaked to island"
        assert any(h["owner_id"] == a_id for h in zs_isl["houses"])

        # Place item on island
        await a.send(json.dumps({"type": "place", "itemType": "tree", "x": 1100, "y": 800}))
        await _recv_until(a, "place", timeout=3)

        # Back inside house -> should only see chair, not tree
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs2, _ = await _recv_until(a, "zone_state", timeout=3)
        types = [it["type"] for it in zs2["items"]]
        assert "chair" in types, "chair missing in house zone_state"
        assert "tree" not in types, "island item leaked into house"


@pytest.mark.asyncio
async def test_zone_scoped_presence_and_move():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, _ = await _join(a, "Alice")
        b_id, _ = await _join(b, "Bob")
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await _recv_until(b, "house", timeout=3)
        await _drain(a, 0.3); await _drain(b, 0.3)

        # B enters A's house
        await b.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs_b, _ = await _recv_until(b, "zone_state", timeout=3)
        assert zs_b and zs_b["zone"] == f"house:{a_id}"

        # Alice (island) should receive player_leave for Bob AND updated players (no Bob)
        got_leave_or_update = False
        drained_a = await _drain(a, 1.0)
        for m in drained_a:
            if m.get("type") == "player_leave" and m.get("id") == b_id:
                got_leave_or_update = True
            if m.get("type") == "players":
                ids = [p["id"] for p in m["players"]]
                assert b_id not in ids, "Bob should not be in island players after entering house"
                got_leave_or_update = True
        assert got_leave_or_update, "Alice did not receive leave/players update when Bob entered house"

        # Alice moves on island; Bob (house) should NOT receive
        await a.send(json.dumps({"type": "move", "x": 1100, "y": 800, "dir": "right"}))
        msgs_b = await _drain(b, 1.0)
        assert not any(m.get("type") == "move" and m.get("id") == a_id for m in msgs_b), \
            "move leaked across zones"

        # Third client C enters same house -> move from C must reach Bob
        async with websockets.connect(url) as c:
            c_id, _ = await _join(c, "Carol")
            await c.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
            await _recv_until(c, "zone_state", timeout=3)
            await _drain(b, 0.4)
            await c.send(json.dumps({"type": "move", "x": 500, "y": 500, "dir": "up"}))
            msgs_b2 = await _drain(b, 1.0)
            assert any(m.get("type") == "move" and m.get("id") == c_id for m in msgs_b2), \
                "same-zone move not delivered"


@pytest.mark.asyncio
async def test_persistence_across_reconnect():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "place", "itemType": "lamp", "x": 420, "y": 420}))
        await _recv_until(a, "place", timeout=3)

    # New client joins fresh
    async with websockets.connect(url) as b:
        _, b_init = await _join(b, "Bob")
        houses = b_init.get("houses", [])
        assert any(h["owner_id"] == a_id for h in houses), "house not persisted for new client"
        await b.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs, _ = await _recv_until(b, "zone_state", timeout=3)
        types = [it["type"] for it in zs["items"]]
        assert "lamp" in types, "interior item not persisted for new joiner"

    # REST still returns room
    r = requests.get(f"{BASE_URL}/api/rooms/{code}", timeout=10)
    assert r.status_code == 200
    assert r.json()["room"]["code"] == code
