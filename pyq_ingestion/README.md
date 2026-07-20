# PYQ Ingestion Pipeline

Populates `gate_questions` from a shared Drive folder containing:
- `GATE PYQ answers/filter1_volume{1,2,3}.pdf` — GATEOverflow compiled books (topic-organized, embedded text, has Answer Keys, but math-heavy MCQ options often extract blank)
- `CS/CS/*.pdf` — original year-wise scanned papers 2007-2026 (real OCR'd option text, but no answer keys)

## Pipeline

1. **Extract a compiled-book chapter's raw text** (e.g. via `pypdf`, given a page range for one chapter — find boundaries by searching for chapter heading text).
2. **`extract_compiled_chapter.py <chapter.txt>`** — parses the trailing "Answer Keys" list via regex (reliable), splits the body into per-question blocks by title occurrence, and sends batches to Groq (structuring only — never inventing missing content) to produce `pyq_prototype_output.json`.
3. **`finalize_and_insert.py <pooler_db_password>`** — classifies each question's gradability from its `answer_raw` value (not the LLM's own `type` field, which is unreliable when no explicit tag was present), skips ungradable ones (no answer, or MCQ/MSQ with fully blank options), and upserts the rest into `gate_questions`.
4. **`ocr_year_papers.py`** — downloads and OCRs the year-wise papers in `CS/CS/`, caching each to `cs_ocr_cache/<filename>.txt` (slow — several minutes per large file; skips files already cached).
5. **`enrich_options_from_year_papers.py <pooler_db_password>`** — for any MCQ/MSQ with blank option slots, searches the matching year's cached OCR text for the question's own text and extracts the `(A)...(D)...` block that follows. Matches by content, not question number (numbering isn't always consistent between sources). Works well for prose-based questions; math-heavy ones often stay incomplete since OCR can't reliably recover embedded formulas.

## Known limitations

- Direct Postgres connection (`db.<ref>.supabase.co`) is **IPv6-only** and unreachable from some networks (e.g. corporate). Use the **pooler** connection instead (`aws-*.pooler.supabase.com:6543`, Project Settings → Database → Connection pooling) — that's what these scripts expect.
- 4 of the 23 year papers are corrupted PDFs and can't be OCR'd at all (`CS2011`, `CS2012`, `CS1-2017`, `CS2-2021`).
- Only ~19% of questions per compiled-book chapter end up gradable (most are descriptive/proof questions with no single answer, or MCQs with unrecoverable math options). NAT (numeric fill-in-blank) questions are unaffected by this and extract reliably.
- As of the last run: only the Graph Theory chapter of volume 1 has been processed. The rest of volume 1, and all of volumes 2-3, remain to be ingested chapter by chapter using the same pipeline.
