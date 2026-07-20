-- Run this script in the Supabase SQL Editor to set up the PYQ Questions & attempts tables.

-- 1. Create gate_questions table
create table if not exists public.gate_questions (
    id uuid default gen_random_uuid() primary key,
    year int not null,
    question_number int not null, -- leading numeric part only, for sorting/display; NOT a unique key (see original_label)
    original_label text, -- the true source identifier, e.g. "38", "9d", "1.25" — old GATE papers used non-integer numbering
    set_label text, -- "Set 1"/"Set 2"/null — some years split into multiple sessions that restart numbering
    subject text,
    type text check (type in ('MCQ', 'MSQ', 'NAT', 'DESCRIPTIVE')),
    question_text text not null,
    options jsonb, -- e.g. {"A": "...", "B": "..."} or null for NAT/DESCRIPTIVE
    correct_answer jsonb not null, -- e.g. ["A"] for MCQ, ["A", "C"] for MSQ, or {"value": N} / {"min":a,"max":b} for NAT
    explanation text,
    marks int default 1,
    created_at timestamptz default now(),
    unique (year, subject, original_label, set_label)
);

-- 2. Create gate_exam_attempts table
create table if not exists public.gate_exam_attempts (
    id uuid default gen_random_uuid() primary key,
    user_id text not null, -- references user's Firebase UUID
    year int not null,
    status text check (status in ('in_progress', 'completed')),
    started_at timestamptz default now(),
    completed_at timestamptz,
    user_answers jsonb, -- e.g. {"1": "A", "2": ["A", "C"], "3": "12.5"}
    score float,
    created_at timestamptz default now()
);

-- 3. Create indexes for quick querying
create index if not exists gate_questions_year_idx on public.gate_questions(year);
create index if not exists gate_exam_attempts_user_id_idx on public.gate_exam_attempts(user_id);
