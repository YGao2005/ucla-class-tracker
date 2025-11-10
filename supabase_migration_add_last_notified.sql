-- Migration: Add last_notified_enrolled column to prevent notification spam
-- This tracks the enrollment number we last notified users about

ALTER TABLE class_states
ADD COLUMN IF NOT EXISTS last_notified_enrolled INTEGER DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN class_states.last_notified_enrolled IS
'Enrollment count when we last sent notifications. Used to prevent spam when status stays Open.';
