# Changelog

## 1.0.0

Initial release. Alliance Auth 5.x compatible replacement for
`allianceauth-mumble-tagger`.

- Tags resolved at authentication time by wrapping `MumbleUser.display_name`
  instead of writing to the database.
- Prefix and suffix tag positions.
- Explicit ordering for users holding multiple tags.
- Deduplication when a tag is reachable through several groups.
- Cached tag index with signal-driven invalidation.
- Self-disables with a clear log message if Alliance Auth changes the
  `display_name` property shape.
