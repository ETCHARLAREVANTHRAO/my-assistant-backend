# PYQ Exam Feature — Progress Tracker

## ✅ What Has Been Done

### 1. Architecture & Design
- Designed full system architecture for the interactive PYQ (Previous Year Questions) exam feature.
- Defined JSON schema for structured question storage (question text, options, correct answer, explanation, subject, marks).
- Designed two new Supabase tables: `gate_questions` and `gate_exam_attempts`.

### 2. GO-PDFs Generator Folder
- Added `GO-PDFs-gatecse-2027/` to this backend repo.
- This contains the MLCFlow automation scripts that compile HTML dumps from GATEOverflow into offline PDFs.
- The HTML files (not included — private to GATEOverflow) are the cleanest source for structured question parsing.

### 3. Database Schema
- Created `supabase_pyq_setup.sql` with:
  - `gate_questions` table — stores year, question number, subject, type (MCQ/MSQ/NAT), question text, options, correct answers, explanations, marks.
  - `gate_exam_attempts` table — stores per-user exam sessions, answers, scores, and status.
- **ACTION REQUIRED**: Run this SQL in your Supabase SQL Editor to create the tables.

### 4. PDF Parser Script
- Wrote regex-based PDF parser (`parse_and_ingest_pyqs.py`) that:
  - Reads GATE solution PDFs from `D:\Desktop files\Gate imp\Gate papers\` (2019–2023).
  - Extracts questions, options (A/B/C/D), correct answers, and explanations.
  - Auto-classifies each question's subject (OS, Networks, Algorithms, DBMS, etc.).
  - Uploads parsed questions directly to Supabase `gate_questions` table.
- **ACTION REQUIRED**: Run `parse_and_ingest_pyqs.py` after database setup.

---

## ❌ What Still Needs To Be Done

### Backend (`exam-rag-backend`)
- [ ] **Run Supabase setup SQL**: Open Supabase → SQL Editor → paste & run `supabase_pyq_setup.sql`.
- [ ] **Run the ingestion script**: `python parse_and_ingest_pyqs.py` to parse local PDFs and populate `gate_questions` table.
- [ ] **Update Groq API key** in `exam-rag-backend/.env` — current key is expired. Get a new one at https://console.groq.com
- [ ] The 3 new API endpoints are already written in `exam-rag-backend/app/routes/pyq.py`:
  - `GET /pyq/years` — list available years + user's best score
  - `GET /pyq/exam/{year}` — fetch all questions for a year (no answer keys sent to client)
  - `POST /pyq/exam/{year}/submit` — grade answers and return solutions

### Mobile App (`my-assistant-mobile`)
- [ ] **Add PYQ API service** to `src/services/api.ts`:
  - `pyqApi.getYears(userId)`
  - `pyqApi.getExam(year)`
  - `pyqApi.submitExam(year, userId, answers)`
- [ ] **Build Year Selector screen** — grid of cards showing year, user best score, status badge.
- [ ] **Build Exam Interface screen** — 3-hour timer, question view with MCQ/NAT inputs, question number drawer (green/grey/yellow).
- [ ] **Build Results / Review screen** — score breakdown, subject-wise analytics, per-question correct/wrong review.
- [ ] **Add navigation** — wire up the new screens to the existing tab/stack navigator.

### Data Quality Improvements
- [ ] Handle MSQ (Multiple Select Questions) parsing — currently defaults to MCQ.
- [ ] Handle NAT (Numerical Answer Type) questions with decimal range grading.
- [ ] Parse GATEOverflow HTML book files for richer, more accurate Q&A extraction.
- [ ] Add 2024 and 2025 question papers when available locally.

---

## 📁 File Reference

| File | Location | Purpose |
|------|----------|---------|
| `supabase_pyq_setup.sql` | `my-assistant-backend/` | Run in Supabase SQL Editor to create DB tables |
| `parse_and_ingest_pyqs.py` | Scratch/scripts folder | Parse local PDFs → upload to Supabase |
| `app/routes/pyq.py` | `exam-rag-backend/` | FastAPI endpoints for PYQ feature |
| `GO-PDFs-gatecse-2027/` | `my-assistant-backend/` | GATEOverflow PDF generation pipeline scripts |
