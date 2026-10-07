"""
Backend tests for Iteration 7: Museum/Cafe zones + Road paving + enter_zone(island, x, y).
"""
import asyncio
import json
import os
import uuid
import pytest
import requests
import websockets

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
WS_BASE = BASE_URL.replace("http", "ws", 1)


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_MuseumCafeRoads"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["code"]


async def _recv_until(ws, mtype, timeout=5.0):
    end = asyncio.get_event_loop().time() + timeout
    others = []
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


# ---------- Museum / Cafe zone tests ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("zone_name,label", [("museum", "Museum"), ("cafe", "Cafe")])
async def test_enter_museum_or_cafe_payload(zone_name, label):
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "enter_zone", "zone": zone_name}))
        zs, _ = await _recv_until(a, "zone_state", timeout=4)
        assert zs is not None, "no zone_state"
        assert zs["zone"] == zone_name
        assert zs["label"] == label
        # Interior spawn ~ HOUSE_SPAWN
        assert zs["you"]["x"] == 450 and zs["you"]["y"] == 480
        assert zs["house"] is None, "museum/cafe must not have house info"
        assert zs["items"] == [] or isinstance(zs["items"], list)
        # Island-only arrays should be empty in interior zones
        assert zs["roads"] == []
        assert zs["crops"] == []
        assert zs["houses"] == []


@pytest.mark.asyncio
async def test_museum_and_cafe_are_isolated_shared_zones():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, _ = await _join(a, "Alice")
        b_id, _ = await _join(b, "Bob")
        await _drain(a); await _drain(b)

        # Both enter museum -> shared presence
        await a.send(json.dumps({"type": "enter_zone", "zone": "museum"}))
        await _recv_until(a, "zone_state", timeout=3)
        await b.send(json.dumps({"type": "enter_zone", "zone": "museum"}))
        zs_b, _ = await _recv_until(b, "zone_state", timeout=3)
        ids = [p["id"] for p in zs_b["players"]]
        assert a_id in ids and b_id in ids, f"museum presence missing: {ids}"

        # Place an item in museum
        await a.send(json.dumps({"type": "place", "itemType": "chair", "x": 400, "y": 400}))
        placed, _ = await _recv_until(a, "place", timeout=3)
        assert placed and placed["item"]["type"] == "chair"

        # Enter cafe -> should NOT contain museum chair
        await a.send(json.dumps({"type": "enter_zone", "zone": "cafe"}))
        zs_cafe, _ = await _recv_until(a, "zone_state", timeout=3)
        assert all(it["type"] != "chair" or it["x"] != 400 for it in zs_cafe["items"]), \
            "museum item leaked into cafe"

        # Go to island -> item not on island
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs_isl, _ = await _recv_until(a, "zone_state", timeout=3)
        assert all(it["type"] != "chair" or it["x"] != 400 for it in zs_isl["items"]), \
            "museum item leaked onto island"

        # Back to museum -> item still there
        await a.send(json.dumps({"type": "enter_zone", "zone": "museum"}))
        zs_m2, _ = await _recv_until(a, "zone_state", timeout=3)
        types = [(it["type"], it["x"]) for it in zs_m2["items"]]
        assert ("chair", 400) in types, f"museum item not persisted: {types}"


# ---------- enter_zone island with explicit x,y ----------

@pytest.mark.asyncio
async def test_enter_zone_island_with_explicit_xy_clamps():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        await a.send(json.dumps({"type": "enter_zone", "zone": "museum"}))
        await _recv_until(a, "zone_state", timeout=3)

        # Exit back to island near museum building
        await a.send(json.dumps({"type": "enter_zone", "zone": "island", "x": 700, "y": 520}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs["zone"] == "island"
        assert zs["you"]["x"] == 700 and zs["you"]["y"] == 520

        # Now clamp test: out-of-bounds coords
        await a.send(json.dumps({"type": "enter_zone", "zone": "cafe"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "enter_zone", "zone": "island", "x": -500, "y": 999999}))
        zs2, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs2["you"]["x"] == 40, f"min clamp failed: {zs2['you']}"
        assert zs2["you"]["y"] == 1500 - 40, f"max clamp failed: {zs2['you']}"


@pytest.mark.asyncio
async def test_house_exit_still_spawns_in_front_of_house():
    """Regression: enter_zone back to island with no x,y and last_house -> spawn in front of house."""
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        # Move Alice to a known island spot so her house gets built there
        await a.send(json.dumps({"type": "move", "x": 1200, "y": 900, "dir": "down"}))
        await asyncio.sleep(0.2)
        await a.send(json.dumps({"type": "build_house"}))
        house_msg, _ = await _recv_until(a, "house", timeout=3)
        assert house_msg
        hx = house_msg["house"]["x"]
        hy = house_msg["house"]["y"]
        # Enter house
        await a.send(json.dumps({"type": "enter_zone", "zone": f"house:{a_id}"}))
        await _recv_until(a, "zone_state", timeout=3)
        # Exit without x/y
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        assert zs["you"]["x"] == hx and zs["you"]["y"] == hy + 70, \
            f"expected in-front-of-house spawn, got {zs['you']}"


# ---------- Roads ----------

@pytest.mark.asyncio
async def test_place_road_broadcast_dedup_persist():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        a_id, _ = await _join(a, "Alice")
        b_id, _ = await _join(b, "Bob")
        await _drain(a); await _drain(b)

        # Place a road
        await a.send(json.dumps({"type": "place_road", "x": 500, "y": 500}))
        a_road, _ = await _recv_until(a, "road", timeout=3)
        b_road, _ = await _recv_until(b, "road", timeout=3)
        assert a_road and b_road, "road broadcast missing"
        assert a_road["road"]["x"] == 500 and a_road["road"]["y"] == 500
        assert "id" in a_road["road"]

        # Duplicate -> NO-OP, no broadcast
        await a.send(json.dumps({"type": "place_road", "x": 500, "y": 500}))
        dup_a, _ = await _recv_until(a, "road", timeout=1.2)
        dup_b, _ = await _recv_until(b, "road", timeout=1.2)
        assert dup_a is None and dup_b is None, "duplicate road broadcast - dedup violated"

        # Different tile -> broadcast
        await a.send(json.dumps({"type": "place_road", "x": 544, "y": 500}))
        a_r2, _ = await _recv_until(a, "road", timeout=3)
        assert a_r2 is not None

        # Persistence via init
        async with websockets.connect(url) as c:
            _, init = await _join(c, "Carol")
            coords = {(r["x"], r["y"]) for r in init.get("roads", [])}
            assert (500, 500) in coords and (544, 500) in coords, f"roads not persisted: {coords}"

        # And via zone_state(island)
        await a.send(json.dumps({"type": "enter_zone", "zone": "island"}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        coords2 = {(r["x"], r["y"]) for r in zs.get("roads", [])}
        assert (500, 500) in coords2 and (544, 500) in coords2


@pytest.mark.asyncio
async def test_place_road_ignored_in_interior_zones():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a:
        a_id, _ = await _join(a, "Alice")
        # Enter museum
        await a.send(json.dumps({"type": "enter_zone", "zone": "museum"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "place_road", "x": 700, "y": 700}))
        no_road, _ = await _recv_until(a, "road", timeout=1.2)
        assert no_road is None, "place_road should be ignored in museum"

        # Enter cafe
        await a.send(json.dumps({"type": "enter_zone", "zone": "cafe"}))
        await _recv_until(a, "zone_state", timeout=3)
        await a.send(json.dumps({"type": "place_road", "x": 701, "y": 701}))
        no_road2, _ = await _recv_until(a, "road", timeout=1.2)
        assert no_road2 is None, "place_road should be ignored in cafe"

        # Return to island with x,y
        await a.send(json.dumps({"type": "enter_zone", "zone": "island", "x": 1000, "y": 500}))
        zs, _ = await _recv_until(a, "zone_state", timeout=3)
        coords = {(r["x"], r["y"]) for r in zs.get("roads", [])}
        assert (700, 700) not in coords and (701, 701) not in coords, \
            f"interior place_road leaked into island roads: {coords}"
