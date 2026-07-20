# PYQ Exam Feature — Progress Tracker

## ✅ What Has Been Done

### 1. Architecture — revised
Originally planned as a separate `exam-rag-backend` service; **consolidated into the existing `my-assistant-backend`** instead (reuses the same Supabase project, Firebase auth, and patterns already in place). The `exam-rag-backend` repo referenced in earlier notes is not part of this plan anymore.

### 2. Database Schema
`supabase_pyq_setup.sql` creates:
- `gate_questions` — year, subject, type (MCQ/MSQ/NAT/DESCRIPTIVE), question text, options, correct answer, marks. Unique key is `(year, subject, original_label, set_label)` — `question_number` alone isn't reliable since old GATE papers use non-integer numbering (`9d`, `1.25`) and some years split into multiple sets that restart numbering.
- `gate_exam_attempts` — per-user exam sessions, answers, scores.
- Both tables are live in Supabase (created via the pooler connection — see `pyq_ingestion/README.md` for why the direct connection doesn't work from this network).

### 3. Ingestion Pipeline (`pyq_ingestion/`)
Working end-to-end, validated on one chapter:
- `extract_compiled_chapter.py` — parses a GATEOverflow compiled-book chapter (Answer Keys via regex, question structuring via LLM — never inventing missing content).
- `finalize_and_insert.py` — classifies gradability from the answer value itself, upserts into `gate_questions`.
- `ocr_year_papers.py` — OCRs the original year-wise scanned papers (`CS/CS/*.pdf` in the shared Drive folder).
- `enrich_options_from_year_papers.py` — fills blank MCQ options by cross-referencing the OCR'd year papers, matching by question content.

**Validated result:** Graph Theory chapter (volume 1) → 17 gradable questions ingested, 3 of 4 MCQs enriched with real option text from year papers.

---

## ❌ What Still Needs To Be Done

### Ingestion — most of the corpus remains
- [ ] Process the rest of `filter1_volume1.pdf`'s chapters (Combinatorics, Mathematical Logic, and whatever else volume 1 covers beyond Graph Theory)
- [ ] Process `filter1_volume2.pdf` and `filter1_volume3.pdf` entirely (likely Algorithms, OS, DBMS, Networks, TOC, Digital Logic, COA, etc.)
- [ ] Same pipeline (`extract_compiled_chapter.py` → `finalize_and_insert.py` → `enrich_options_from_year_papers.py`) applies to each chapter — just needs the page-range/chapter-boundary lookup repeated per chapter
- [ ] Repair or re-source the 4 corrupted year papers (`CS2011`, `CS2012`, `CS1-2017`, `CS2-2021`) if better copies become available — currently unreadable by any method
- [ ] 2015 Set 2/3 papers aren't in the Drive folder at all — some enrichment matches can't be attempted for that year

### API endpoints (not started)
- [ ] `GET /pyq/years` — list available years + user's best score
- [ ] `GET /pyq/exam/{year}` — fetch questions for a year (no answer keys sent to client)
- [ ] `POST /pyq/exam/{year}/submit` — grade answers, return solutions, write to `gate_exam_attempts`

### Web app (`my-assistant-mobile/web/`)
- [ ] Wire the existing (currently mock-data) Quiz pages to these real endpoints
- [ ] Build a year/exam selector, timed exam interface, and results/review screen

### Data quality
- [ ] Only ~19% of source questions per chapter end up gradable at present (mostly NAT) — MCQ/MSQ yield is much lower due to blank math options in the compiled book. Enrichment from year papers helps prose-based questions only.
