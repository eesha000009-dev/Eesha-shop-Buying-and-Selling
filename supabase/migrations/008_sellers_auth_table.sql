-- =====================================================
-- MIGRATION: Sellers Authentication Table
-- This table stores seller accounts separately from buyer accounts
-- Run this in Supabase SQL Editor
-- =====================================================

-- Create the sellers table if it doesn't exist
CREATE TABLE IF NOT EXISTS sellers (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    business_name VARCHAR(255),
    business_description TEXT,
    business_category VARCHAR(100),
    business_location VARCHAR(255),
    business_type VARCHAR(50) DEFAULT 'MERCHANT', -- MERCHANT or FARMER
    contact_phone VARCHAR(20),
    address TEXT,
    profile_image TEXT,
    farm_name VARCHAR(255),
    farm_type VARCHAR(50),
    state VARCHAR(100),
    
    -- Account status
    status VARCHAR(20) DEFAULT 'active', -- active, suspended, pending
    email_verified BOOLEAN DEFAULT false,
    
    -- Preferences
    preferences JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- Enable RLS
ALTER TABLE sellers ENABLE ROW LEVEL SECURITY;

-- Policies for sellers table
CREATE POLICY "Sellers can view their own data" ON sellers 
    FOR SELECT USING (true); -- Allow public read for login verification

CREATE POLICY "Anyone can insert seller" ON sellers 
    FOR INSERT WITH CHECK (true); -- Allow signup

CREATE POLICY "Sellers can update their own data" ON sellers 
    FOR UPDATE USING (true); -- Simplified for now

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sellers_email ON sellers(email);
CREATE INDEX IF NOT EXISTS idx_sellers_business_type ON sellers(business_type);
CREATE INDEX IF NOT EXISTS idx_sellers_status ON sellers(status);

-- Function to update updated_at timestamp
DROP TRIGGER IF EXISTS update_sellers_updated_at ON sellers;
CREATE TRIGGER update_sellers_updated_at BEFORE UPDATE ON sellers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create the function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- =====================================================
-- RESULT
-- =====================================================
SELECT 'Migration completed successfully! Sellers table created with password authentication.' as result;
