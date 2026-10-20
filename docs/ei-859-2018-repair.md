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
or mastery records are replaced. Reference answers remain original answer pages;
this repair does not claim per-question answer matching or completion of other
859 years.

Verification: Django source/linear-selected tests, frontend unit tests and build,
and authenticated browser checks at desktop/mobile widths. Browser checks cover
the reported old URL, explicit original view, all thirty individual images, the
restored judgement section, cross-page waveforms, and the heatmap excluding the
archived parent. Test sessions do not submit attempts or mastery updates.
