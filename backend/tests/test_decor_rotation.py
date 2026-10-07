"""
Backend tests for iteration 3 features:
- set_decor owner-only + persistence + zone broadcast
- Decor delivery on enter_zone (house_info)
- build_house defaults floor=wood, wall=cream
- Furniture rotation persistence (0/90/180/270)
- New furniture types: bed, rug, bookshelf, plant
- Island spawn-in-front after exiting house (x==house.x, y==house.y+70)
- Zone isolation for decor broadcasts
"""
import asyncio
import json
import os
import uuid
import pytest
import requests
import websockets

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
WS_BASE = BASE_URL.replace("http", "ws", 1)


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_Decor"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["code"]


async def _recv_until(ws, mtype, timeout=5.0):
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


async def _drain(ws, duration=0.5):
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
    assert init is not None
    return pid, init


@pytest.mark.asyncio
async def test_build_house_default_decor():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "build_house"}))
        h, _ = await _recv_until(a, "house", timeout=3)
        assert h is not None
        assert h["house"].get("floor") == "wood"
        assert h["house"].get("wall") == "cream"
        # enter_zone also includes house info with defaults
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs["house"]["floor"] == "wood"
        assert zs["house"]["wall"] == "cream"
        assert zs["house"]["owner_id"] == a_id


@pytest.mark.asyncio
async def test_set_decor_owner_only_persist_and_broadcast():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, _ = await _join(a, "Alice")
        b_id, _ = await _join(b, "Bob")
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await _recv_until(b, "house", timeout=3)
        # Alice (owner) enters her house
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        # Bob (non-owner visitor) enters Alice's house
        await b.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(b, "zone_state", timeout=3)
        await _drain(a, 0.4); await _drain(b, 0.4)

        # Owner sets decor
        await a.send(json.dumps({"type": "set_decor", "floor": "mint", "wall": "lavender"}))
        a_dec, _ = await _recv_until(a, "decor", timeout=3)
        b_dec, _ = await _recv_until(b, "decor", timeout=3)
        assert a_dec and a_dec["floor"] == "mint" and a_dec["wall"] == "lavender"
        assert b_dec and b_dec["floor"] == "mint" and b_dec["wall"] == "lavender"

        # Persistence: new client enters A's house -> gets updated decor
        async with websockets.connect(url) as c:
            await _join(c, "Carol")
            await c.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
            zs, _ = await _recv_until(c, "zone_state", timeout=3)
            assert zs["house"]["floor"] == "mint"
            assert zs["house"]["wall"] == "lavender"

        # Non-owner tries to change decor -> ignored
        await b.send(json.dumps({"type": "set_decor", "floor": "pink", "wall": "blue"}))
        a_dec2, _ = await _recv_until(a, "decor", timeout=1.5)
        b_dec2, _ = await _recv_until(b, "decor", timeout=1.5)
        assert a_dec2 is None, "non-owner decor should not broadcast"
        assert b_dec2 is None

        # Re-verify persistence still mint/lavender
        async with websockets.connect(url) as d:
            await _join(d, "Dan")
            await d.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
            zs, _ = await _recv_until(d, "zone_state", timeout=3)
            assert zs["house"]["floor"] == "mint"
            assert zs["house"]["wall"] == "lavender"


@pytest.mark.asyncio
async def test_decor_zone_isolation():
    """Decor broadcast must only reach players in that house zone, not island."""
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, _ = await _join(a, "Alice")
        _, _ = await _join(b, "Bob")  # Bob stays on island
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await _recv_until(b, "house", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        await _drain(b, 0.4)
        await a.send(json.dumps({"type": "set_decor", "floor": "stone", "wall": "blue"}))
        a_dec, _ = await _recv_until(a, "decor", timeout=3)
        assert a_dec is not None
        # Bob (island) must NOT get decor
        b_msgs = await _drain(b, 1.0)
        assert not any(m.get("type") == "decor" for m in b_msgs), "decor leaked to island"


@pytest.mark.asyncio
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
async def test_rotation_persistence(rotation):
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "place", "itemType": "chair", "x": 1050, "y": 760, "rotation": rotation}))
        placed, _ = await _recv_until(a, "place", timeout=3)
        assert placed is not None
        assert placed["item"]["rotation"] == rotation
        # Verify via REST GET
        r = requests.get(f"{BASE_URL}/api/rooms/{code}", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        match = [it for it in items if it["id"] == placed["item"]["id"]]
        assert match and match[0]["rotation"] == rotation
        # Verify via zone_state
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        zs_match = [it for it in zs["items"] if it["id"] == placed["item"]["id"]]
        assert zs_match and zs_match[0]["rotation"] == rotation


@pytest.mark.asyncio
@pytest.mark.parametrize("itype", ["bed", "rug", "bookshelf", "plant"])
async def test_new_furniture_types(itype):
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "place", "itemType": itype, "x": 430, "y": 430, "rotation": 90}))
        placed, _ = await _recv_until(a, "place", timeout=3)
        assert placed and placed["item"]["type"] == itype
        assert placed["item"]["rotation"] == 90
        # Re-enter to verify persistence
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        types = [it["type"] for it in zs["items"]]
        assert itype in types


@pytest.mark.asyncio
async def test_island_spawn_in_front_after_exit():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        # Move Alice somewhere unique before building
        await a.send(json.dumps({"type": "move", "x": 1234, "y": 876, "dir": "down"}))
        await asyncio.sleep(0.2)
        await a.send(json.dumps({"type": "build_house"}))
        h, _ = await _recv_until(a, "house", timeout=3)
        assert h is not None
        hx = h["house"]["x"]
        hy = h["house"]["y"]
        # house.y should be player.y - 40 == 836
        assert hx == 1234
        assert hy == 876 - 40
        # Enter house
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        # Exit back to island -> spawn at (hx, hy+70)
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs["you"]["x"] == hx, f"expected x={hx}, got {zs['you']['x']}"
        assert zs["you"]["y"] == hy + 70, f"expected y={hy+70}, got {zs['you']['y']}"


@pytest.mark.asyncio
async def test_set_decor_from_island_ignored():
    """Owner trying to set_decor while on island (not inside own house zone) is ignored."""
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "build_house"}))
        await _recv_until(a, "house", timeout=3)
        # Alice still on island -> should be ignored
        await a.send(json.dumps({"type": "set_decor", "floor": "pink", "wall": "blue"}))
        dec, _ = await _recv_until(a, "decor", timeout=1.5)
        assert dec is None
        # Verify defaults still apply
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs["house"]["floor"] == "wood"
        assert zs["house"]["wall"] == "cream"
