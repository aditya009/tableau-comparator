# Negative test-data pack — SharePoint ingestion pipeline

Five files, each built to trigger one specific failure/edge path the current evidence pack
doesn't cover. Drop them into SharePoint as described below, run the pipeline, then capture
the same kind of evidence the original 17-screenshot pack used (before/after volume state,
reconciliation log, ingestion_status_table_v2 row, and any error message) for each.

| File | Closes | What it's built to do |
|---|---|---|
| `corrupt_workbook.xlsx` | **TC-11** | A real `.xlsx` truncated mid-archive — has a valid file signature (Excel recognises it as "Excel 2007+" by its magic bytes) but no end-of-file record, so `openpyxl`/pandas/Excel itself cannot open it. Confirmed unreadable before packaging. |
| `unsupported_filetype.pdf` | **TC-19** | A fully valid, parseable one-page PDF (confirmed with `pypdf`) — content doesn't matter, only that its extension isn't `.csv`/`.xlsx`. |
| `headerless_data.csv` | **TC-34** | Same column shape as the real `hmrc-exrates-*.csv` files, but with the header row removed — just raw data rows from line 1. |
| `empty_file.csv` | **TC-34** (bonus) | A genuine 0-byte file — the other half of "structural validation": no header *and* no content. |
| `orphan_no_metadata.csv` | **TC-29** | A perfectly well-formed CSV. Its "no resolvable metadata" state comes entirely from *where* you place it, not its content — see placement notes below. |

## How to place each one

**1. `corrupt_workbook.xlsx` → drop into an existing tested folder (e.g. `QPS_Index/`)**
alongside the files already there. Run the pipeline once. Expected: this file fails and is
logged with an error in `ingestion_status_table_v2`; every other file in that same run still
ingests successfully (proves TC-11 — one bad file doesn't block the rest).

**2. `unsupported_filetype.pdf` → drop into the same tested folder** (e.g. `QPS_Index/`) next
to the csv/xlsx files. Run the pipeline. Expected: the pipeline never attempts to process it
(no status row, no landed copy) and a warning is logged noting the file type was skipped
(closes TC-19). If no warning appears at all — only silence — that itself is worth raising,
since AC5 explicitly asks for a *logged* warning, not just silent exclusion.

**3. `headerless_data.csv` and `empty_file.csv` → drop into the same tested folder.** Run the
pipeline. Expected: both are rejected with a clear validation error rather than being silently
loaded (an empty/headerless load would otherwise either crash the activity or create a table
with garbage/no columns) — closes TC-34 for both the "no header" and "empty" cases in one run.

**4. `orphan_no_metadata.csv` → create a brand-new subfolder with nothing else in it** (e.g.
`QPS_Index/NoMetadataTest/`) and drop only this file inside — no folder-level `_metadata.yml`,
no same-name `orphan_no_metadata.yml`. This is the one file where placement *is* the test:
if you put it anywhere a `_metadata.yml` already applies, it will resolve metadata from that
default and the negative case never fires. Run the pipeline. Expected: ingestion is blocked
for this file specifically, with an error logged (closes TC-29 — the core governance gate that
currently has zero negative evidence).

## After the run

For each file, capture: (a) its row (or absence of a row) in `ingestion_status_table_v2`,
(b) the corresponding line in the reconciliation log, and (c) the actual error/warning text.
Then update `SP_Ingestion_Test_Cases.xlsx`: flip TC-11, TC-19, TC-29 and TC-34 from
"Not Evidenced" to "Evidenced" (or to a bug reference, if the actual behaviour doesn't match
what's expected above) in the Tester Actual Result / Bug-Clarification columns.

## What this pack does *not* close

These "Not Evidenced" gaps need a second/modified **run**, not a new file, so they aren't
included here: incremental detection and watermark skipping (TC-12/13/14/31 — re-run with no
source changes, then re-run with one file modified), hour-gating (TC-05/07/08 — needs runs at
different clock hours), schema evolution (TC-24 — needs a second run of an existing file with
an added column), a genuinely invalid **config** section rather than a bad file (TC-04), and
per-project `trigger_hours` (TC-45 — needs `qps_index` and `hmrc_test` reconfigured with
different hour windows before any file drop will help).
