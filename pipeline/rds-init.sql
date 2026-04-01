-- ==========================================
-- 1. Create Independent/Reference Tables
-- ==========================================

CREATE TABLE IF NOT EXISTS council (
    council_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    council_name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS status_type (
    status_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status_type VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS application_type (
    application_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_type VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_type (
    decision_type_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    decision_type VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriber (
    subscriber_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    postcode VARCHAR(10) NOT NULL,
    lat NUMERIC(10, 7),
    long NUMERIC(10, 7),
    radius_miles NUMERIC(2, 1) DEFAULT 0.5,
    min_interest_score INTEGER DEFAULT 1 
        CHECK (min_interest_score BETWEEN 1 AND 5),
    min_score_disturbance INTEGER DEFAULT 1
        CHECK (min_score_disturbance BETWEEN 1 AND 5),
    min_score_scale INTEGER DEFAULT 1
        CHECK (min_score_scale BETWEEN 1 AND 5),
    min_score_housing INTEGER DEFAULT 1
        CHECK (min_score_housing BETWEEN 1 AND 5),
    min_score_environment INTEGER DEFAULT 1
        CHECK (min_score_environment BETWEEN 1 AND 5),
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ
);

-- ==========================================
-- 2. Create Dependent Tables
-- ==========================================

CREATE TABLE IF NOT EXISTS application (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    council_id BIGINT NOT NULL,
    status_type_id BIGINT NOT NULL,
    application_type_id BIGINT NOT NULL,
    application_number VARCHAR(100),
    validation_date DATE,
    address VARCHAR(255),
    postcode VARCHAR(20),
    lat NUMERIC(10, 7), 
    long NUMERIC(10, 7),
    ai_summary TEXT,
    public_interest_score BIGINT,
    score_disturbance INTEGER
        CHECK (score_disturbance BETWEEN 1 AND 5),
    score_scale INTEGER
        CHECK (score_scale BETWEEN 1 AND 5),
    score_housing INTEGER
        CHECK (score_housing BETWEEN 1 AND 5),
    score_environment INTEGER
        CHECK (score_environment BETWEEN 1 AND 5),
    application_page_url TEXT,
    document_page_url TEXT,
    decided_at TIMESTAMPTZ,
    decision_type_id BIGINT,
    
    -- Foreign Key Constraints
    CONSTRAINT fk_council
        FOREIGN KEY (council_id) 
        REFERENCES council (council_id)
        ON DELETE CASCADE,
        
    CONSTRAINT fk_status_type
        FOREIGN KEY (status_type_id) 
        REFERENCES status_type (status_type_id),
        
    CONSTRAINT fk_application_type
        FOREIGN KEY (application_type_id) 
        REFERENCES application_type (application_type_id),
        
    CONSTRAINT fk_decision_type
        FOREIGN KEY (decision_type_id)
        REFERENCES decision_type (decision_type_id)
);

-- ==========================================
-- 3. Create Indexes for Performance
-- ==========================================

-- Foreign Key Indexes (Crucial for JOIN performance and cascading deletes)
CREATE INDEX IF NOT EXISTS idx_application_council_id ON application(council_id);
CREATE INDEX IF NOT EXISTS idx_application_status_type_id ON application(status_type_id);
CREATE INDEX IF NOT EXISTS idx_application_application_type_id ON application(application_type_id);

-- Search Indexes (Optimized for common lookup patterns)
CREATE INDEX IF NOT EXISTS idx_application_number ON application(application_number);
CREATE INDEX IF NOT EXISTS idx_application_coordinates ON application(lat, long);

-- Subscriber Indexes
CREATE INDEX IF NOT EXISTS idx_subscriber_email ON subscriber(email);
-- Partial index optimized for querying only active subscribers
CREATE INDEX IF NOT EXISTS idx_active_subscriber ON subscriber(email) WHERE unsubscribed_at IS NULL;