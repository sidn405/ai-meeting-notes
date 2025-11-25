-- Database Migration for Subscriptions
-- Run this in your PostgreSQL database

-- 1. Add stripe_customer_id to portaluser table if it doesn't exist
ALTER TABLE portaluser 
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_portaluser_stripe_customer 
ON portaluser(stripe_customer_id);

-- 2. Create subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES portaluser(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES project(id) ON DELETE SET NULL,
    
    -- Stripe identifiers
    stripe_subscription_id VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) NOT NULL,
    stripe_price_id VARCHAR(255) NOT NULL,
    
    -- Plan details
    plan_id VARCHAR(100) NOT NULL,
    plan_name VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    interval VARCHAR(50) DEFAULT 'month',
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'active',
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    
    -- Dates
    start_date TIMESTAMP NOT NULL,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    last_payment_date TIMESTAMP,
    cancelled_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata (for additional info)
    metadata TEXT
);

-- 3. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_subscriptions_user 
ON subscriptions(user_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_project 
ON subscriptions(project_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_subscription 
ON subscriptions(stripe_subscription_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer 
ON subscriptions(stripe_customer_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_status 
ON subscriptions(status);

CREATE INDEX IF NOT EXISTS idx_subscriptions_created 
ON subscriptions(created_at DESC);

-- 4. Create trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_subscriptions_updated_at 
    BEFORE UPDATE ON subscriptions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Add check constraint for valid statuses
ALTER TABLE subscriptions 
ADD CONSTRAINT check_subscription_status 
CHECK (status IN ('active', 'past_due', 'cancelled', 'incomplete', 'trialing', 'unpaid'));
