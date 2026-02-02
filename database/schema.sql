-- AIropa Database Schema

-- Articles table for scraped content
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    published_date TEXT,
    scraped_date TEXT DEFAULT (datetime('now')),
    is_processed BOOLEAN DEFAULT FALSE,
    quality_score REAL DEFAULT 0.0,
    category TEXT,
    country TEXT,
    language TEXT DEFAULT 'en',
    hash TEXT UNIQUE NOT NULL
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON articles(published_date);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(hash);

-- Content generation tracking
CREATE TABLE IF NOT EXISTS generated_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    markdown_file TEXT NOT NULL,
    generation_date TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

-- Scraping logs for monitoring
CREATE TABLE IF NOT EXISTS scraping_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT DEFAULT (datetime('now')),
    source TEXT NOT NULL,
    articles_found INTEGER DEFAULT 0,
    articles_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0.0
);

-- Quality assessment results
CREATE TABLE IF NOT EXISTS quality_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    assessment_date TEXT DEFAULT (datetime('now')),
    relevance_score REAL DEFAULT 0.0,
    quality_score REAL DEFAULT 0.0,
    credibility_score REAL DEFAULT 0.0,
    overall_score REAL DEFAULT 0.0,
    notes TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);