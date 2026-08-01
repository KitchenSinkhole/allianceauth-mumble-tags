import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class MumbleTagsConfig(AppConfig):
    name = "mumbletags"
    label = "mumbletags"
    verbose_name = "Mumble Tags"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from . import signals  # noqa: F401  (registers cache invalidation)
        from .app_settings import mumble_active

        if not mumble_active():
            logger.warning(
                "Alliance Auth's Mumble service is not in INSTALLED_APPS; mumbletags will do nothing."
            )
            return

        from allianceauth.services.modules.mumble.models import MumbleUser

        from .tagging import patch_display_name

        patch_display_name(MumbleUser)
