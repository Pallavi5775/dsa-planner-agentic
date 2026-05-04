-- Run once against your PostgreSQL database to add hint support
ALTER TABLE dsa.questions
    ADD COLUMN IF NOT EXISTS hint TEXT;

ALTER TABLE dsa.practice_logs
    ADD COLUMN IF NOT EXISTS hint_used BOOLEAN NOT NULL DEFAULT FALSE;

-- Question description (AI-generated, stored per question)
ALTER TABLE dsa.questions
    ADD COLUMN IF NOT EXISTS description TEXT;

-- Pattern notes (per-user, per-pattern study notes + memory tricks)
CREATE TABLE IF NOT EXISTS dsa.user_pattern_notes (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER NOT NULL REFERENCES dsa.users(id) ON DELETE CASCADE,
    pattern            VARCHAR NOT NULL,
    notes              TEXT    NOT NULL DEFAULT '',
    memory_techniques  TEXT    NOT NULL DEFAULT '',
    CONSTRAINT uq_pattern_note_user UNIQUE (user_id, pattern)
);
