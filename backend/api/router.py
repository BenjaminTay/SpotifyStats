"""Top-level API router — all sub-routers are mounted here."""

from fastapi import APIRouter

from backend.api.analysis import router as analysis_router
from backend.api.dashboard import router as dashboard_router
from backend.api.timeline import router as timeline_router
from backend.api.leaderboard import router as leaderboard_router
from backend.api.behavior import router as behavior_router
from backend.api.listening_hours import router as listening_hours_router
from backend.api.artist_deep import router as artist_deep_router
from backend.api.wrapped import router as wrapped_router
from backend.api.library import router as library_router
from backend.api.search import router as search_router
from backend.api.insights import router as insights_router
from backend.api.podcast import router as podcast_router
from backend.api.video import router as video_router
from backend.api.profile import router as profile_router
from backend.api.wrapped_hub import router as wrapped_hub_router
from backend.api.settings import router as settings_router
from backend.api.billboard import router as billboard_router
from backend.api.version_merge import router as version_merge_router
from backend.api.import_ import router as import_router
from backend.api.lyrics import router as lyrics_router
from backend.api.music import router as music_router
from backend.api.account import router as account_router
from backend.api.spotify_auth import router as spotify_auth_router

api_router = APIRouter()

api_router.include_router(analysis_router)
api_router.include_router(dashboard_router)
api_router.include_router(timeline_router)
api_router.include_router(leaderboard_router)
api_router.include_router(behavior_router)
api_router.include_router(listening_hours_router)
api_router.include_router(artist_deep_router)
api_router.include_router(wrapped_router)
api_router.include_router(library_router)
api_router.include_router(search_router)
api_router.include_router(insights_router)
api_router.include_router(podcast_router)
api_router.include_router(video_router)
api_router.include_router(profile_router)
api_router.include_router(wrapped_hub_router)
api_router.include_router(settings_router)
api_router.include_router(billboard_router)
api_router.include_router(version_merge_router)
api_router.include_router(import_router)
api_router.include_router(lyrics_router, prefix="/lyrics", tags=["Lyrics"])
api_router.include_router(music_router)
api_router.include_router(account_router)
api_router.include_router(spotify_auth_router)
