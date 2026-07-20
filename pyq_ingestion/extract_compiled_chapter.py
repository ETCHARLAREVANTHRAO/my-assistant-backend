"""
Extracts a single chapter's worth of questions from a GATEOverflow compiled
book (e.g. filter1_volume1.pdf), given its raw text (question body + trailing
"Answer Keys" list). Parses the Answer Keys via regex (reliable), and uses an
LLM only to structure each question block (never to invent missing content —
math-heavy option text is often genuinely blank in the source PDF).

Usage: python extract_compiled_chapter.py <chapter_text_file.txt>
Writes pyq_prototype_output.json for finalize_and_insert.py to consume.
"""
import re, json, os, sys
import httpx
from dotenv import load_dotenv
load_dotenv('../.env')
from groq import Groq

if len(sys.argv) != 2:
    print("Usage: python extract_compiled_chapter.py <chapter_text_file.txt>", file=sys.stderr)
    sys.exit(1)

client = Groq(api_key=os.getenv('GROQ_API_KEY'), http_client=httpx.Client(verify=False))

with open(sys.argv[1], encoding='utf-8') as f:
    text = f.read()
body, _, answer_section = text.partition('Answer Keys')

# Parse answer keys (reliable regex, no LLM needed)
answer_pairs = re.findall(r'(\d+\.\d+\.\d+)\s*\n(.+)', answer_section)

# Split question blocks by title occurrence
pattern = re.compile(r'[A-Za-z ]+: GATE (?:CSE|IT) [\w0-9 |Set]+\| Question: [\w.,]+')
matches = list(pattern.finditer(body))
blocks = []
for i, m in enumerate(matches):
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(body)
    blocks.append(body[start:end].strip())

print(f'{len(blocks)} question blocks, {len(answer_pairs)} answer key entries', file=sys.stderr)
assert len(blocks) == len(answer_pairs), "Mismatch! Need manual review."

SYSTEM_PROMPT = """You extract structured GATE Computer Science exam questions from raw PDF-extracted text of a compiled reference book. The extraction has rendering artifacts: mathematical symbols/equations are sometimes missing or blank, and MCQ options sometimes show as bare "A . B . C . D ." with no actual text if the original option was a mathematical expression that didn't extract as text.

Your job is to CLEANLY STRUCTURE exactly what is present. Never invent, guess, or fill in missing question content, option text, or values. If an option has no visible/recoverable text, set its value to null. Reproduce question text as extracted, including any gaps from missing math.

For each block, output an object with:
- title: the topic/title line before the colon (e.g. "Graph Coloring")
- year: the GATE year as an integer (extract from "GATE CSE YYYY" or tags like "gatecse-YYYY", "gateNNNN"). If a Set is mentioned (Set 1/Set 2), still just extract the numeric year.
- set_label: "Set 1"/"Set 2" if mentioned, else null
- question_number: the value after "Question:" in the title (a string, e.g. "38", "9c", "16-b")
- tags: array of the lowercase hyphenated tags found near the end of the block (e.g. ["graph-theory","graph-coloring","normal","two-marks"])
- type: one of "MCQ", "MSQ", "NAT", "DESCRIPTIVE" — infer from tags: "multiple-selects"->MSQ, "numerical-answers"->NAT, "descriptive"->DESCRIPTIVE, otherwise MCQ if options are present else DESCRIPTIVE
- marks: 2 if tags include "two-marks", else 1
- question_text: the actual question stem, cleaned of tag lines and junk, preserving any [gap] where math content is missing
- options: an object like {"A": "...", "B": "...", "C": "...", "D": "..."} with actual extracted text, or null for any option with no recoverable text, or null entirely if the question has no options (NAT/DESCRIPTIVE)

Return a JSON object: {"questions": [ ... ]} with exactly one entry per input block, in the same order."""

def process_batch(batch_blocks, batch_num):
    user_content = "\n\n---BLOCK SEPARATOR---\n\n".join(
        f"[BLOCK {i}]\n{b}" for i, b in enumerate(batch_blocks)
    )
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract these {len(batch_blocks)} question blocks:\n\n{user_content}"},
        ],
        response_format={"type": "json_object"},
        max_tokens=8000,
        temperature=0,
    )
    result = json.loads(resp.choices[0].message.content)
    questions = result.get("questions", [])
    print(f'Batch {batch_num}: sent {len(batch_blocks)}, got {len(questions)}', file=sys.stderr)
    return questions

BATCH_SIZE = 15
all_questions = []
for i in range(0, len(blocks), BATCH_SIZE):
    batch = blocks[i:i+BATCH_SIZE]
    qs = process_batch(batch, i // BATCH_SIZE)
    all_questions.extend(qs)

print(f'Total extracted: {len(all_questions)}', file=sys.stderr)

# Stitch with answer keys by position
final = []
for (idx, ans), q in zip(answer_pairs, all_questions):
    final.append({
        "chapter_index": idx,
        "answer_raw": ans,
        **q,
    })

with open('pyq_prototype_output.json', 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)

print('Saved', len(final), 'stitched questions to pyq_prototype_output.json', file=sys.stderr)
