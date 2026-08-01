from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import TagAssociation
from .tagging import invalidate_tag_cache

# Note: user group membership changes need no invalidation -- the cache only
# holds the tag->group mapping, and a user's groups are read live at auth time.


@receiver(post_save, sender=TagAssociation)
@receiver(post_delete, sender=TagAssociation)
def _tag_changed(sender, **kwargs) -> None:
    invalidate_tag_cache()


@receiver(m2m_changed, sender=TagAssociation.groups.through)
def _tag_groups_changed(sender, action, **kwargs) -> None:
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_tag_cache()
