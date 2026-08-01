from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import gettext_lazy as _


class TagAssociation(models.Model):
    """A tag appended to the Mumble display name of members of the given groups."""

    class Position(models.TextChoices):
        PREFIX = "prefix", _("Prefix")
        SUFFIX = "suffix", _("Suffix")

    tag = models.CharField(
        _("Tag"),
        max_length=32,
        unique=True,
        help_text=_("Text added to the display name, e.g. [FC] or ~AFK~"),
    )
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="mumble_tags",
        verbose_name=_("Groups"),
        help_text=_("Members of any of these groups receive this tag."),
    )
    enabled = models.BooleanField(_("Enabled"), default=True)
    position = models.CharField(
        _("Position"),
        max_length=6,
        choices=Position.choices,
        default=Position.SUFFIX,
        help_text=_("Prefix tags sort users together in the Mumble channel list."),
    )
    order = models.SmallIntegerField(
        _("Order"),
        default=0,
        help_text=_("Lower values appear first when a user has several tags."),
    )

    class Meta:
        verbose_name = _("Tag association")
        verbose_name_plural = _("Tag associations")
        ordering = ["order", "tag"]

    def __str__(self) -> str:
        return self.tag
