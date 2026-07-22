from .audio import register_audio_routes
from .campaigns import register_campaign_routes
from .characters import register_character_routes
from .clipboard import register_clipboard_routes
from .demo import register_demo_routes
from .fallback import register_fallback_routes
from .favorites import register_favorite_routes
from .gods import register_god_routes
from .generators import register_generator_routes
from .jobs import register_job_routes
from .maps import register_map_routes
from .notes import register_note_routes
from .party import register_party_routes
from .resources import register_resource_routes
from .rules import register_rule_routes
from .scenes import register_scene_routes
from .settings import register_setting_routes
from .spotlight import register_spotlight_routes


def register_domain_routes(bp, views: dict) -> None:
    register_campaign_routes(bp, views)
    register_map_routes(bp, views)
    register_scene_routes(bp, views)
    register_audio_routes(bp, views)
    register_resource_routes(bp, views)
    register_generator_routes(bp, views)
    register_job_routes(bp, views)
    register_rule_routes(bp, views)
    register_character_routes(bp, views)
    register_party_routes(bp, views)
    register_note_routes(bp, views)
    register_god_routes(bp, views)
    register_setting_routes(bp, views)
    register_demo_routes(bp, views)
    register_favorite_routes(bp, views)
    register_spotlight_routes(bp, views)
    register_clipboard_routes(bp, views)
    register_fallback_routes(bp, views)
