-- Profile photo storage key (same upload_dir layout as product media; bucket implied "local").
ALTER TABLE ryunova_users
  ADD COLUMN IF NOT EXISTS avatar_s3_key VARCHAR(512);
