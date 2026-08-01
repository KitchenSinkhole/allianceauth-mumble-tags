"""Tag resolution and the MumbleUser.display_name patch.

The design hinges on one fact about Alliance Auth 5.x: ``MumbleUser.display_name``
is a read-only property computed at authentication time, not a database column.
So there is nothing to write and nothing to keep in sync -- we simply wrap the
property and append tags on the way out.
"""

import logging

from django.core.cache import cache

from .app_settings import MUMBLETAGS_CACHE_TTL
from .models import TagAssociation

logger = logging.getLogger(__name__)

CACHE_KEY = "mumbletags:index:v1"


def _tag_index() -> dict[int, list[tuple[str, int, str]]]:
    """Map ``group_pk -> [(position, order, tag), ...]`` for enabled tags.

    Cached because the authenticator is a long-lived process that hits this on
    every single connect. Invalidated by signals, so the TTL is only a backstop.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    index: dict[int, list[tuple[str, int, str]]] = {}
    associations = TagAssociation.objects.filter(enabled=True).prefetch_related("groups")
    for association in associations:
        entry = (association.position, association.order, association.tag)
        # .all() rather than .values_list() so the prefetch is actually used
        for group in association.groups.all():
            index.setdefault(group.pk, []).append(entry)

    cache.set(CACHE_KEY, index, MUMBLETAGS_CACHE_TTL)
    return index


def invalidate_tag_cache() -> None:
    cache.delete(CACHE_KEY)


def tags_for_user(user) -> list[tuple[str, int, str]]:
    """Resolve the tag entries a user qualifies for, deduplicated and ordered."""
    index = _tag_index()
    if not index:
        return []

    found: set[tuple[str, int, str]] = set()
    for group_pk in user.groups.values_list("pk", flat=True):
        found.update(index.get(group_pk, ()))

    return sorted(found, key=lambda entry: (entry[1], entry[2]))


def build_display_name(base: str, entries: list[tuple[str, int, str]]) -> str:
    """Assemble ``[prefixes] base [suffixes]``, skipping empty segments."""
    prefix = " ".join(tag for position, _, tag in entries if position == TagAssociation.Position.PREFIX)
    suffix = " ".join(tag for position, _, tag in entries if position == TagAssociation.Position.SUFFIX)
    return " ".join(part for part in (prefix, base, suffix) if part)


def patch_display_name(model) -> bool:
    """Wrap ``model.display_name`` so it appends group tags.

    Returns True if the patch was applied. We deliberately wrap the *existing*
    getter rather than reimplementing NameFormatter, so any upstream change to
    how the base name is built is inherited for free.
    """
    existing = model.__dict__.get("display_name")

    if not isinstance(existing, property) or existing.fget is None:
        logger.error(
            "%s.display_name is not a readable property (got %r). "
            "Alliance Auth's Mumble service has likely changed; mumbletags is disabled.",
            model.__name__,
            type(existing).__name__,
        )
        return False

    if getattr(existing.fget, "_mumbletags_patched", False):
        return True  # ready() can fire more than once in some setups

    base_getter = existing.fget

    def tagged_display_name(self) -> str:
        base = base_getter(self)
        try:
            entries = tags_for_user(self.user)
        except Exception:
            # Never let a tagging failure block a user from connecting.
            logger.exception("Failed to resolve Mumble tags for %r; falling back to untagged name.", self.user)
            return base
        if not entries:
            return base
        return build_display_name(base, entries)

    tagged_display_name._mumbletags_patched = True
    model.display_name = property(tagged_display_name)
    logger.info("Patched %s.display_name with mumbletags.", model.__name__)
    return True
