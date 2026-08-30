-- channel_id must be nullable because some touchpoints legitimately have no matching marketing channel
-- (e.g., unusual traffic source/medium combinations), and the pipeline deliberately keeps those rows
-- rather than silently dropping them.
ALTER TABLE customer_touchpoints ALTER COLUMN channel_id DROP NOT NULL;
