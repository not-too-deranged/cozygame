"""
Backend tests for iteration 5: fish WS handler.
- On island: 'fish' returns wallet with 'caught' + 'caught_value' and bells increase strictly by caught_value.
- Catch name must be in FISH pool; value must match pool mapping.
- In house zone: fish is ignored (no bells change).
- Fish wallet message is scoped to the acting player only.
"""
import asyncio
import json
import os
import uuid

import pytest
import requests
import websockets
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")
WS_BASE = BASE_URL.replace("http", "ws", 1)

FISH_VALUES = {"Carp": 16, "Sea Bass": 22, "Red Snapper": 34, "Golden Trout": 60, "Old Boot": 3}


def _create_room():
    r = requests.post(f"{BASE_URL}/api/rooms/create", json={"name": "TEST_Fish"}, timeout=15)
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


async def _join(ws, name="Angler", pid=None):
    pid = pid or str(uuid.uuid4())
    await ws.send(json.dumps({"type": "join", "player": {"id": pid, "name": name, "color": "#FF9AA2", "border": "#E06873"}}))
    init = await _recv_until(ws, "init", timeout=5)
    assert init is not None
    return pid, init


@pytest.mark.asyncio
async def test_fish_credits_bells_with_caught_fields():
    code = _create_room()
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        _, init = await _join(ws, "Angler")
        bells = init["wallet"]["bells"]
        # Fish 6 times, verify strict increase and consistency
        for _ in range(6):
            await ws.send(json.dumps({"type": "fish"}))
            w = await _recv_until(ws, "wallet", 3)
            assert w is not None, "no wallet received after fish"
            assert "caught" in w and "caught_value" in w, f"missing caught fields: {w}"
            assert w["caught"] in FISH_VALUES, f"unknown fish {w['caught']}"
            assert w["caught_value"] == FISH_VALUES[w["caught"]], "value mismatch for species"
            assert w["bells"] == bells + w["caught_value"], f"bells not strictly increased: before={bells} after={w['bells']} +{w['caught_value']}"
            bells = w["bells"]


@pytest.mark.asyncio
async def test_fish_ignored_in_house_zone():
    code = _create_room()
    pid = str(uuid.uuid4())
    async with websockets.connect(f"{WS_BASE}/api/ws/{code}") as ws:
        await _join(ws, "Angler", pid=pid)
        # Build & enter house
        await ws.send(json.dumps({"type": "build_house"}))
        await _recv_until(ws, "house", 3)
        await ws.send(json.dumps({"type": "enter_zone", "zone": f"house:{pid}"}))
        zs = await _recv_until(ws, "zone_state", 3)
        assert zs and zs["zone"] == f"house:{pid}"
        await _drain(ws, 0.3)
        # Attempt to fish inside house - should be ignored
        await ws.send(json.dumps({"type": "fish"}))
        w = await _recv_until(ws, "wallet", 1.5)
        assert w is None, f"fish worked in house zone: {w}"


@pytest.mark.asyncio
async def test_fish_scoped_to_actor_only():
    code = _create_room()
    url = f"{WS_BASE}/api/ws/{code}"
    async with websockets.connect(url) as a, websockets.connect(url) as b:
        await _join(a, "Alice")
        await _join(b, "Bob")
        await _drain(a, 0.3); await _drain(b, 0.3)
        await a.send(json.dumps({"type": "fish"}))
        wa = await _recv_until(a, "wallet", 3)
        assert wa and "caught" in wa
        msgs = await _drain(b, 1.0)
        assert not any(m.get("type") == "wallet" for m in msgs), "fish wallet leaked"
