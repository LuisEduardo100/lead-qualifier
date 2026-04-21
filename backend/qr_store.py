import asyncio

_store: dict[str, str] = {}
_events: dict[str, asyncio.Event] = {}


def set_qr(instance: str, base64: str):
    _store[instance] = base64
    ev = _events.get(instance)
    if ev:
        ev.set()


def clear_qr(instance: str):
    _store.pop(instance, None)
    _events.pop(instance, None)


async def wait_for_qr(instance: str, timeout: float = 20.0) -> str | None:
    if _store.get(instance):
        return _store[instance]
    ev = _events.setdefault(instance, asyncio.Event())
    try:
        await asyncio.wait_for(asyncio.shield(ev.wait()), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return _store.get(instance)
