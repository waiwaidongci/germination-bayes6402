-- Initial schema uses SQLAlchemy metadata; optional upgrade indexes:
CREATE INDEX lot_study_code_idx ON seed_lots (study_id,code);
CREATE INDEX note_run_status_idx ON sampling_notes (run_id,status);
