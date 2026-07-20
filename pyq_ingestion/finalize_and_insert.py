"""
Reads pyq_prototype_output.json (from extract_compiled_chapter.py), classifies
each question's gradability from its answer_raw value, and upserts the
gradable ones into gate_questions.

Usage: python finalize_and_insert.py <pooler_db_password>
"""
import json, os, re, sys
import psycopg2
from psycopg2.extras import Json

if len(sys.argv) != 2:
    print("Usage: python finalize_and_insert.py <pooler_db_password>", file=sys.stderr)
    sys.exit(1)
DB_PASSWORD = sys.argv[1]

with open('pyq_prototype_output.json', encoding='utf-8') as f:
    data = json.load(f)

def classify_answer(raw):
    """Derive (type, parsed_answer) from the answer_raw string itself — reliable,
    since it came from clean regex parsing of the Answer Keys list. Don't trust
    the LLM's own 'type' field, which defaults inconsistently when no explicit
    tag (numerical-answers/multiple-selects/descriptive) was present."""
    raw = raw.strip()
    if raw in ('N/A', 'X', 'TBA', ''):
        return 'SKIP', None
    if re.fullmatch(r'[A-E](;[A-E])*', raw):
        letters = raw.split(';')
        return ('MSQ' if len(letters) > 1 else 'MCQ'), letters
    if ':' in raw:
        lo, hi = [p.strip() for p in raw.split(':', 1)]
        try:
            return 'NAT', {"min": float(lo), "max": float(hi)}
        except ValueError:
            return 'UNKNOWN', {"raw": raw}
    try:
        val = float(raw)
        return 'NAT', {"value": int(val) if val.is_integer() else val}
    except ValueError:
        return 'UNKNOWN', {"raw": raw}

rows = []
counts = {'skip_no_answer': 0, 'skip_blank_mcq': 0, 'skip_unknown': 0, 'kept': 0}

for q in data:
    qtype, parsed_answer = classify_answer(q['answer_raw'])

    if qtype == 'SKIP':
        counts['skip_no_answer'] += 1
        continue
    if qtype == 'UNKNOWN':
        counts['skip_unknown'] += 1
        continue
    if qtype in ('MCQ', 'MSQ'):
        opts = q.get('options') or {}
        if not any(v for v in opts.values()):
            counts['skip_blank_mcq'] += 1
            continue

    original_label = q['question_number']
    qnum_match = re.match(r'\d+', original_label)
    question_number = int(qnum_match.group()) if qnum_match else 0

    rows.append({
        "year": q['year'],
        "question_number": question_number,
        "original_label": original_label,
        "set_label": q.get('set_label'),
        "subject": q['title'],
        "type": qtype,
        "question_text": q['question_text'],
        "options": q['options'] if qtype in ('MCQ', 'MSQ') else None,
        "correct_answer": parsed_answer,
        "explanation": None,
        "marks": q['marks'],
    })
    counts['kept'] += 1

print(counts, file=sys.stderr)

conn = psycopg2.connect(
    host='aws-1-ap-southeast-2.pooler.supabase.com', port=6543, dbname='postgres',
    user='postgres.fulptpqiztwrntktkrff', password=DB_PASSWORD, connect_timeout=15,
)
with conn.cursor() as cur:
    for r in rows:
        cur.execute("""
            insert into gate_questions (year, question_number, original_label, set_label, subject, type, question_text, options, correct_answer, explanation, marks)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (year, subject, original_label, set_label) do update set
                question_number = excluded.question_number,
                type = excluded.type,
                question_text = excluded.question_text,
                options = excluded.options,
                correct_answer = excluded.correct_answer,
                marks = excluded.marks
        """, (
            r['year'], r['question_number'], r['original_label'], r['set_label'], r['subject'], r['type'], r['question_text'],
            Json(r['options']) if r['options'] is not None else None,
            Json(r['correct_answer']), r['explanation'], r['marks'],
        ))
conn.commit()

with conn.cursor() as cur:
    cur.execute("select count(*) from gate_questions")
    print('Total rows in gate_questions now:', cur.fetchone()[0], file=sys.stderr)
conn.close()
