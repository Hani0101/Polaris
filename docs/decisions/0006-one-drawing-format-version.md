---
status: accepted
---

# One drawing format version

Versions 2 to 6 each exist to allow one more element kind: marks (3), a description (4), math and code (5), and graphs (6). Each new kind added a version, a version set in `api/polaris/whiteboard.py`, and a sentence in the whiteboard rules.

From version 7 on, a new drawing is version 7 and every element kind is checked on its own terms. A new kind or a new field is added to version 7 without a new version. Version 7 requires a description, as 4, 5, and 6 do. Labels inside boxes and arrows attached to elements exist only on version 7.

Versions 2 to 6 still open and keep the rules they were written with, so a stored drawing never changes meaning. Marks on a version 7 drawing keep it version 7.

The alternative was a version 7 for labels and attached arrows, then a version 8 for the next kind. It was rejected: the version number stopped saying anything a reader needs, and every new kind touched the version rules for every older kind.
