from unittest.mock import patch as mock_patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from mumbletags.models import TagAssociation
from mumbletags.tagging import invalidate_tag_cache, patch_display_name


class StubMumbleUser:
    """Mimics allianceauth.services.modules.mumble.models.MumbleUser in AA 5.x:
    a read-only display_name property computed from the linked auth User."""

    def __init__(self, user):
        self.user = user

    @property
    def display_name(self) -> str:
        return f"[TEST]{self.user.username}"


class TaggingTestCase(TestCase):
    def setUp(self):
        invalidate_tag_cache()

        class Model(StubMumbleUser):
            pass

        Model.display_name = StubMumbleUser.__dict__["display_name"]
        self.Model = Model
        self.assertTrue(patch_display_name(Model))

        self.user = User.objects.create(username="Pilot")
        self.fc = Group.objects.create(name="FC")
        self.logi = Group.objects.create(name="Logi")

    def _name(self):
        invalidate_tag_cache()
        return self.Model(self.user).display_name

    def test_no_tags_leaves_name_untouched(self):
        self.assertEqual(self._name(), "[TEST]Pilot")

    def test_suffix_tag_applied(self):
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        self.assertEqual(self._name(), "[TEST]Pilot [FC]")

    def test_prefix_and_suffix(self):
        pre = TagAssociation.objects.create(tag="**", position=TagAssociation.Position.PREFIX)
        pre.groups.add(self.fc)
        suf = TagAssociation.objects.create(tag="[LOGI]")
        suf.groups.add(self.logi)
        self.user.groups.add(self.fc, self.logi)
        self.assertEqual(self._name(), "** [TEST]Pilot [LOGI]")

    def test_tag_from_two_groups_is_not_duplicated(self):
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc, self.logi)
        self.user.groups.add(self.fc, self.logi)
        self.assertEqual(self._name(), "[TEST]Pilot [FC]")

    def test_order_is_respected(self):
        first = TagAssociation.objects.create(tag="[A]", order=1)
        first.groups.add(self.fc)
        second = TagAssociation.objects.create(tag="[B]", order=-5)
        second.groups.add(self.logi)
        self.user.groups.add(self.fc, self.logi)
        self.assertEqual(self._name(), "[TEST]Pilot [B] [A]")

    def test_disabled_tag_ignored(self):
        tag = TagAssociation.objects.create(tag="[FC]", enabled=False)
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        self.assertEqual(self._name(), "[TEST]Pilot")

    def test_tag_disappears_when_user_leaves_group(self):
        """The bug the upstream fork was trying to fix -- free here, since
        nothing is persisted and groups are read live."""
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        self.assertEqual(self._name(), "[TEST]Pilot [FC]")

        self.user.groups.remove(self.fc)
        self.assertEqual(self._name(), "[TEST]Pilot")

    def test_m2m_change_invalidates_cache_without_manual_flush(self):
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        self.assertEqual(self.Model(self.user).display_name, "[TEST]Pilot [FC]")

        tag.groups.remove(self.fc)  # signal must flush the cache
        self.assertEqual(self.Model(self.user).display_name, "[TEST]Pilot")

    def test_patch_is_idempotent(self):
        self.assertTrue(patch_display_name(self.Model))
        self.assertTrue(patch_display_name(self.Model))
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        self.assertEqual(self._name(), "[TEST]Pilot [FC]")

    def test_patch_refuses_when_display_name_is_not_a_property(self):
        class Changed:
            display_name = "not a property"

        self.assertFalse(patch_display_name(Changed))
        self.assertEqual(Changed.display_name, "not a property")

    def test_tagging_failure_falls_back_to_base_name(self):
        tag = TagAssociation.objects.create(tag="[FC]")
        tag.groups.add(self.fc)
        self.user.groups.add(self.fc)
        with mock_patch("mumbletags.tagging.tags_for_user", side_effect=RuntimeError("boom")):
            self.assertEqual(self.Model(self.user).display_name, "[TEST]Pilot")
