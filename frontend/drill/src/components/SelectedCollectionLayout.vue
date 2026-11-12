<template><section class="page selected-collection"><slot /></section></template>
<style scoped>
.selected-collection { min-width:0; }
.selected-collection :deep(.selected-notice) { margin:12px 0; color:var(--text-secondary); font-size:13px; line-height:1.6; }
.selected-collection :deep(.selected-notice summary), .selected-collection :deep(.selected-filter-disclosure > summary) { display:flex; align-items:center; gap:8px; min-height:44px; cursor:pointer; list-style:none; font-size:14px; }
.selected-collection :deep(.selected-notice summary::after), .selected-collection :deep(.selected-filter-disclosure > summary::after) { content:'⌄'; color:var(--text-secondary); }
.selected-collection :deep(.selected-notice p) { margin:0 0 12px; }
.selected-collection :deep(.selected-filter-disclosure) { margin:8px 0 16px; }
.selected-collection :deep(.selected-filters) { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr)); align-items:end; gap:12px; margin:12px 0; }
.selected-collection :deep(.selected-filters label) { min-width:0; display:grid; gap:8px; font-size:13px; color:var(--text-secondary); }
.selected-collection :deep(.selected-filters select) { min-width:0; width:100%; max-width:100%; min-height:44px; padding:8px; border:1px solid var(--border-control); border-radius:6px; background:var(--surface-page); color:var(--text-primary); font-size:14px; }
.selected-collection :deep(.selected-filters button), .selected-collection :deep(.selected-group header button) { min-height:44px; padding:8px 12px; border:0; border-radius:6px; background:var(--surface-subtle); color:var(--text-primary); font-size:14px; cursor:pointer; }
.selected-collection :deep(.selected-coverage) { margin:16px 0 8px; color:var(--text-secondary); font-size:13px; line-height:1.6; font-variant-numeric:tabular-nums; }
.selected-collection :deep(.selected-group) { padding:20px 0 0; margin:24px 0; border:0; border-top:1px solid var(--border-subtle); border-radius:0; background:transparent; }
.selected-collection :deep(.selected-group > header) { display:flex; justify-content:space-between; align-items:start; gap:12px; margin:0 0 12px; }
.selected-collection :deep(.selected-group > header > div) { min-width:0; }
.selected-collection :deep(.selected-group h2) { margin:4px 0; font-size:17px; line-height:1.4; }
.selected-collection :deep(.selected-group p) { margin:8px 0 0; color:var(--text-secondary); font-size:13px; line-height:1.6; }
.selected-collection :deep(.selected-question-grid) { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr)); gap:4px 16px; margin-top:12px; }
.selected-collection :deep(.selected-question-grid > button) { position:relative; min-width:0; display:flex; flex-wrap:wrap; align-items:baseline; align-content:start; gap:4px 8px; padding:12px 8px; border:0; border-bottom:1px solid var(--border-subtle); border-radius:4px; box-shadow:none; background:transparent; color:var(--text-primary); text-align:left; overflow-wrap:anywhere; cursor:pointer; }
.selected-collection :deep(.selected-question-grid > button:hover) { background:var(--surface-hover); }
.selected-collection :deep(.selected-question-grid > button.selected) { outline:1px solid var(--text-primary); outline-offset:-1px; background:var(--surface-selected); }
.selected-collection :deep(.selected-question-grid > button:focus-visible) { outline:2px solid var(--accent-focus); outline-offset:2px; }
.selected-collection :deep(.selected-question-grid strong) { flex:1; min-width:80px; font-size:14px; font-weight:600; }
.selected-collection :deep(.selected-question-grid > button > small:not(.exam-type-badge)) { flex-basis:100%; }
.selected-collection :deep(.selected-question-grid small), .selected-collection :deep(.selected-question-grid span), .selected-collection :deep(.selected-question-grid em) { font-size:12px; line-height:1.5; color:var(--text-secondary); font-style:normal; }
.selected-collection :deep(.selected-state) { display:inline-flex; align-items:center; gap:6px; }
.selected-collection :deep(.selected-state::before) { content:''; width:6px; height:6px; border-radius:50%; background:var(--text-tertiary); }
.selected-collection :deep(.mastered .selected-state::before) { background:var(--status-success); }
.selected-collection :deep(.review .selected-state::before) { background:var(--status-review); }
.selected-collection :deep(.selected-question-grid.compact) { grid-template-columns:repeat(auto-fill,minmax(32px,1fr)); gap:4px; }
.selected-collection :deep(.selected-question-grid.compact > button) { display:grid; min-height:36px; align-content:center; justify-items:center; padding:4px; border:0; background:var(--surface-subtle); text-align:center; }
.selected-collection :deep(.selected-question-grid.compact > .mastered) { background:var(--status-success-soft); }
.selected-collection :deep(.selected-question-grid.compact > .review) { background:var(--status-review-soft); }
.selected-collection :deep(.selected-question-grid.compact .selected-state) { font-size:0; }
.selected-collection :deep(.selected-question-grid.compact strong) { min-width:0; }
.selected-collection :deep(.selected-question-grid.compact .selected-state::before) { width:4px; height:4px; }
.selected-collection :deep(.selected-legend) { display:flex; gap:16px; align-items:center; flex-wrap:wrap; margin:16px 0; font-size:13px; color:var(--text-secondary); }
.selected-collection :deep(.selected-legend label) { display:flex; align-items:center; gap:8px; min-height:44px; cursor:pointer; }
.selected-collection :deep(.selected-legend .mastered) { color:var(--status-success); }
.selected-collection :deep(.selected-legend .review) { color:var(--status-review); }
.selected-collection :deep(.selected-review) { margin:24px 0; color:var(--text-secondary); line-height:1.7; font-size:13px; }
.selected-collection :deep(.selected-review summary) { min-height:44px; cursor:pointer; }
.selected-collection :deep(.selected-review ul) { list-style:none; padding:0; }
.selected-collection :deep(.selected-review li) { padding:8px 0; border-bottom:1px solid var(--border-subtle); }
@media(pointer:coarse) { .selected-collection :deep(.selected-question-grid.compact) { grid-template-columns:repeat(auto-fill,minmax(44px,1fr)); } .selected-collection :deep(.selected-question-grid.compact > button) { min-height:44px; } }
@media(max-width:600px) { .selected-collection :deep(.selected-filters) { grid-template-columns:repeat(2,minmax(0,1fr)); } .selected-collection :deep(.selected-group > header) { flex-wrap:wrap; } .selected-collection :deep(.selected-filters select) { font-size:16px; } }
</style>
