# 2008 electronics: whole-paper individual question repair

Reported question: `ba43a016-d1fb-56da-9a18-13fb1c4b45cc`, document 25,
question 6. Its answer was already individual, but its stem still fell back to
the five-page original. Only five of the 36 indexed practice units had stems.

The reviewed manifests are `drill_sources/data/electronics_2008_{index,questions,answers}.json`.
They replace this paper's older, incomplete candidate index. The PDF source SHA256
is `f81b0792cea211b579a8300e87bbbd2064eaaee520721078ed55d405abab3879`.
Question pages are 90–94, reference pages 238–243 (zero-based). All eleven pages
were checked against their cached OCR and rendered originals; no new OCR or
whole-book model analysis was needed.

There are 37 practice units: 13 fill-in items, 16 choices, and questions 3–10.
The old index omitted fill-in item 2. Its stable child is added; all existing
36 UUIDs, attempts, notes, states, original assets and revision links remain.
The index is now complete. Original question and reference pages stay accessible.

The question manifest contains 45 regions. Shared diagram bands are retained
for fill-in 8/12 and choice 1/2. Fill-in 10 includes the next-page decoder circuit;
choice 3 includes next-page C/D options. Question 6 contains both the entire
logic circuit and all three input waveforms, including captions. Question 7
keeps its MUX diagram and function table. Two misleading old crops are archived
by exact source ID/hash allowlists, never deleted. Four other existing question
images and all six existing answer images are reused unchanged.

One side-by-side exception is necessary: choice 13's capacitor C is higher than
its stem; its diagram caption extends beside choice 14's stem. A full-width
horizontal cut cannot both retain the figure and exclude neighbouring stems.
The `ei-reviewed-column-figure-v1` profile permits only an explicitly reviewed
two-region stem/figure pair with exact bbox allowlists, role ordering, a reason
and figure label. Ordinary question crops still must retain full page width.

The answer manifest contains 48 regions. Choice answers are original number/
letter cells, not a shared answer table. The `ei-reviewed-answer-table-v1`
profile allows small answer-only cells with a matching item number and A–D
review metadata; it never relaxes question cropping. The seven available
choice explanations and all long-answer diagrams/formulas are retained. Other
choices have only the original answer letter, not invented explanations.
Long answers 3, 5 and 9 continue across pages. Full six-page reference remains
available without leaving the current question.

Apply index and both crop manifests in one outer transaction, with
`--supersede-reviewed` for question crops only. Use source PDFs already on the
target machine. Never transfer a local database snapshot over VPS user progress.
The repair guard verifies all old image bytes/UUIDs/attempt and state IDs and
revision links before committing; repeat execution creates no questions/images.

New PNG payload: 6,621,778 bytes (41 question images and 42 answer images).
No schema migration or frontend rebuild is required. Regression coverage:
78 backend tests, exact reported heatmap URL on desktop/mobile, all 37 API
question/answer pairs, tall circuit, shared/cross-page figures/options, individual
answer cells and original five-/six-page viewers. Browser QA does not submit
attempts or alter mastery records.
