-- =====================================================
-- MIGRATION: Add Authentication Columns to Sellers Table
-- This ONLY adds new columns, does NOT modify existing ones
-- Run this in Supabase SQL Editor
-- =====================================================

-- Add password_hash column for custom authentication
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Add seller_type column to distinguish between MERCHANT and FARMER
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS seller_type VARCHAR(50) DEFAULT 'MERCHANT';

-- Add farm-specific columns (for farmers)
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS farm_name VARCHAR(255);
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS farm_type VARCHAR(50);
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS state VARCHAR(100);

-- Add email verification status
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false;

-- Add last login tracking
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

-- Create index on email for faster login queries
CREATE INDEX IF NOT EXISTS idx_sellers_email ON sellers(email);

-- Create index on seller_type for filtering
CREATE INDEX IF NOT EXISTS idx_sellers_seller_type ON sellers(seller_type);

-- Create index on status
CREATE INDEX IF NOT EXISTS idx_sellers_status ON sellers(status);

-- =====================================================
-- RESULT
-- =====================================================
SELECT 'Migration completed! New columns added to sellers table:
- password_hash (for authentication)
- seller_type (MERCHANT or FARMER)
- farm_name (for farmers)
- farm_type (for farmers)
- state (location)
- email_verified
- last_login_at' as result;
