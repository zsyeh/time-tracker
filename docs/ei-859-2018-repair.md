# 859 2018 individual-question repair

The reported document 26 URL pointed to the original source question, not a
single-question child. Its incomplete index kept it practiceable. The original
index contained 20 anchors, omitted the entire ten-item judgement section, and
only 14 children had reviewed crops.

The reviewed manifests in `drill_sources/data/ucas_859_2018_*.json` cover 30
questions: 10 choice, 10 judgement, 6 fill-in and 4 long-answer questions. All
five original question pages and all sixteen added crop images were visually
checked, including the DSP diagram and the last question's cross-page waveforms.
Existing twenty question identities and seventeen crop images are unchanged.
Sixteen new PNGs require 1,173,959 bytes; original paper/answer images remain.

Only complete EI sources whose every child has its own crop opt into navigation
from the old source URL to the first individual question. `view=original` keeps
the full paper accessible, with a separate individual-question navigation list.
Partial sources and other workspaces retain their existing behavior. No attempt
or mastery records are replaced. The initial question-only repair left reference
answers as original pages; the follow-up below adds per-question matching. This
repair does not claim completion of other 859 years.

Verification: Django source/linear-selected tests, frontend unit tests and build,
and authenticated browser checks at desktop/mobile widths. Browser checks cover
the reported old URL, explicit original view, all thirty individual images, the
restored judgement section, cross-page waveforms, and the heatmap excluding the
archived parent. Test sessions do not submit attempts or mastery updates.

## Individual reference answers

`ucas_859_2018_answers.json` maps each of the same thirty identities to its
printed section/item in the twelve-page answer PDF. All pages lack a text layer;
local Tesseract OCR was cached for anchor discovery only. Equations remain PDF
images, not reconstructed text. The full-width whitespace detector validates
boundaries, including tall summation limits and matrices. All thirty top/bottom
boundaries and the original answer pages were visually checked. Two header-only
continuation slivers are explicitly excluded; no solution content is excluded.

There are 39 answer regions for 30 questions, including 7 cross-page answers.
The fifth long-answer section spans four crops; its graphs precede the sixth
section without merging into it. Added PNG payload is 9,632,153 bytes (database
overhead excluded). All original question/crop/answer images and question UUIDs
are retained, as are attempts, notes and mastery states.

Render with the existing command's explicit answer mode:

```sh
python manage.py render_source_question_regions drill_sources/data/ucas_859_2018_answers.json --source-dir /path/to/sources --asset-type answer_crop --dry-run
```

Remove `--dry-run` after review. The command validates every mapping before
writing, inserts atomically, uses stable answer-specific source IDs, is
idempotent and refuses conflicting existing crops. It never changes progress
rows. No schema migration is required. Individual practice shows the matched
answer; the separate full-answer disclosure lazily fetches the original twelve
pages without navigating away or changing the currently tracked question.
