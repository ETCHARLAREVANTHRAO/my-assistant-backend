"""
Fills blank MCQ/MSQ options in gate_questions by searching the matching
year's OCR'd original exam paper (cs_ocr_cache/, from ocr_year_papers.py)
for the question's own text, then extracting the "(A) ... (B) ..." block
that follows it.

Matches by CONTENT (a substring of question_text), not by question number —
the compiled book's internal numbering doesn't always match the original
paper's own numbering, but the question text is a reliable anchor either way.

Math-heavy questions often still come out empty/garbled here (OCR can't
recover embedded formulas/symbols reliably) — this recovers real option text
for prose-based questions only. Review before trusting math-heavy matches.

Usage: place OCR'd year papers in cs_ocr_cache/<filename>.pdf.txt (via
ocr_year_papers.py) before running this.
"""
import glob
import re
import sys

import psycopg2
from psycopg2.extras import Json

POOLER = dict(
    host="aws-1-ap-southeast-2.pooler.supabase.com",
    port=6543,
    dbname="postgres",
    user="postgres.fulptpqiztwrntktkrff",
    connect_timeout=15,
)


def find_options_block(paper_text: str, question_text: str) -> dict | None:
    """Search paper_text for a distinctive substring of question_text, then
    parse the "(A) ... (B) ... (C) ... (D) ..." block that follows it."""
    anchor = question_text.strip()[:40]
    idx = paper_text.find(anchor)
    if idx == -1:
        return None
    window = paper_text[idx : idx + 1500]
    pattern = re.compile(
        r"\(A\)\s*(.+?)\s*\(B\)\s*(.+?)\s*\(C\)\s*(.+?)\s*\(D\)\s*(.+?)(?:\n\n|\Z)",
        re.DOTALL,
    )
    m = pattern.search(window)
    if not m:
        return None
    return {k: v.strip() for k, v in zip("ABCD", m.groups())}


def year_paper_path(year: int, set_label: str | None) -> str | None:
    candidates = []
    if set_label == "Set 1":
        candidates.append(f"cs_ocr_cache/CS1-{year}.pdf.txt")
        candidates.append(f"cs_ocr_cache/CS1{year}.pdf.txt")
    elif set_label == "Set 2":
        candidates.append(f"cs_ocr_cache/CS2-{year}.pdf.txt")
        candidates.append(f"cs_ocr_cache/CS2{year}.pdf.txt")
    else:
        candidates.append(f"cs_ocr_cache/CS{year}.pdf.txt")
    for c in candidates:
        import os
        if os.path.exists(c):
            return c
    return None


def main(password: str):
    conn = psycopg2.connect(password=password, **POOLER)
    with conn.cursor() as cur:
        cur.execute(
            "select id, year, set_label, question_text, options "
            "from gate_questions where type in ('MCQ','MSQ')"
        )
        rows = cur.fetchall()

    updated = 0
    for row_id, year, set_label, question_text, options in rows:
        if all(options.get(k) for k in "ABCD"):
            continue  # already complete
        path = year_paper_path(year, set_label)
        if not path:
            continue
        with open(path, encoding="utf-8") as f:
            paper_text = f.read()
        found = find_options_block(paper_text, question_text)
        if not found:
            continue
        merged = {k: (options.get(k) or found.get(k)) for k in "ABCD"}
        with conn.cursor() as cur:
            cur.execute(
                "update gate_questions set options = %s where id = %s",
                (Json(merged), row_id),
            )
        updated += 1
        print(f"Enriched {year} (set={set_label}): {question_text[:60]}", file=sys.stderr)
    conn.commit()
    conn.close()
    print(f"Total enriched: {updated}/{len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python enrich_options_from_year_papers.py <db_password>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
