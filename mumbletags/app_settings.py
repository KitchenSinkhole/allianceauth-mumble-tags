from django.conf import settings

# Backstop only -- the cache is invalidated by signals whenever tags change.
MUMBLETAGS_CACHE_TTL = getattr(settings, "MUMBLETAGS_CACHE_TTL", 3600)


def mumble_active() -> bool:
    return "allianceauth.services.modules.mumble" in settings.INSTALLED_APPS
