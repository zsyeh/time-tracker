# 2003 electronics, version 2: complete paper repair

Reported URL: `/practice/414fa8a4-d7f1-552f-abd3-e3ca2215a70f?document=25&topic=1508&unattempted=1`.
This is question 1(5), the voltage-follower circuit, not top-level question 5.
It had no individual image and therefore used the original four-page viewer.

The old index mixed question 1's subitems with top-level questions 8–10 and
omitted questions 2–7. It also contained a 3.3-point-high sliver instead of
question 1(3). Review of the four original question and four reference pages
establishes 16 practice units: 1(1)–1(7), then questions 2–10.

The reviewed index/questions/answers manifests are
`drill_sources/data/electronics_2003_v2_{index,questions,answers}.json`. These
override this paper's entries in the old global index/candidate manifest.
Existing ten UUIDs are retained; six missing questions are added. Labels and
ordering are corrected so next/previous navigation follows the actual paper.

Question regions: 20. Answer regions: 18. Each preserves full PDF width. Specific
checks include the complete voltage-follower diagram for 1(5), cross-page
conditions for 1(6), both feedback circuits and captions for 1(7), the large
adder/RAM reference circuits, and formulas at the bottom of the final answer.
The shared figure band printed above questions 4 and 5 is repeated after their
own stems, preserving their referenced figures 3 and 4. Answer 8 retains a small
amount of preceding context because its handwritten corrections overlap the
margin next to answer 7. Full original paper and full original answers remain
available from every practice unit.

Two defective existing crops (1(2), 1(3)) are explicitly superseded, not deleted.
The renderer requires both `--supersede-reviewed` and exact old source IDs/SHA256
allowlists plus a review reason. The old binaries and PKs remain; existing
revision links still display the old image using their immutable link type.
New revisions exclude superseded assets. Default crop import still refuses
unreviewed conflicts; dry-run does not change any asset types.

Added PNG payload: 2,643,419 bytes (17 new question crops and 18 answer crops).
The three existing complete images for question 1(1) and question 8 are reused.
Verification includes 74 backend regression tests and authenticated desktop/
mobile checks of the exact reported URL, all 16 API question/answer pairs,
cross-page conditions, shared figure bands and both four-page original views.

Apply the order/index repair and both crop manifests atomically. Do not run the
old mixed index over this repaired paper. No schema migration is needed. Existing
attempts, mastery states, notes, old UUIDs, original images and historical
revision links must remain intact. Repeating the repair must create no further
questions or images. Tests cover exact-hash supersession approval, dry-run,
idempotency, image/history preservation and new-revision exclusion.
