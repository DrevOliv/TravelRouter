from fastapi import APIRouter

from ..api_models import SubtitleBody, TrackBody
from ..screen_data import action_payload, remote_payload
from ..system_api import pause_playback, seek_relative, set_audio_track, set_subtitle_track, stop_playback


router = APIRouter()


@router.get("/remote")
async def api_remote():
    return remote_payload()


@router.post("/remote/pause")
async def api_remote_pause():
    result = pause_playback()
    return action_payload("remote_pause", result, "Playback toggled", "Pause failed", refresh="remote")


@router.post("/remote/stop")
async def api_remote_stop():
    result = stop_playback()
    return action_payload("remote_stop", result, "Playback stopped", "Stop failed", refresh="remote")


@router.post("/remote/rewind")
async def api_remote_rewind():
    result = seek_relative(-30)
    return action_payload("remote_rewind", result, "Rewound 30 seconds", "Rewind failed", refresh="remote")


@router.post("/remote/forward")
async def api_remote_forward():
    result = seek_relative(30)
    return action_payload("remote_forward", result, "Skipped forward 30 seconds", "Skip failed", refresh="remote")


@router.post("/remote/audio")
async def api_remote_audio(body: TrackBody):
    result = set_audio_track(body.track_id)
    return action_payload("remote_audio", result, "Audio track changed", "Audio track change failed", refresh="remote")


@router.post("/remote/subtitles")
async def api_remote_subtitles(body: SubtitleBody):
    value = "no" if body.track_id == "no" else int(body.track_id)
    result = set_subtitle_track(value)
    return action_payload("remote_subtitles", result, "Subtitle settings updated", "Subtitle change failed", refresh="remote")
