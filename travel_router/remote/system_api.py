from ..system_apis import get_playback_state


def remote_payload() -> dict:
    return {"playback_state": get_playback_state()}
