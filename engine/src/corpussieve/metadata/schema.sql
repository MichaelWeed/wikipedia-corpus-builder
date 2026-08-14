-- CorpusSieve Metadata SQLite Index Schema v1

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    page_id INTEGER PRIMARY KEY,
    page_namespace INTEGER NOT NULL,
    title TEXT NOT NULL,
    is_redirect INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS category_membership (
    category TEXT NOT NULL,
    page_id INTEGER NOT NULL,
    member_type TEXT NOT NULL,
    PRIMARY KEY (category, page_id)
);

CREATE TABLE IF NOT EXISTS categories (
    category TEXT PRIMARY KEY,
    page_id INTEGER
);

CREATE TABLE IF NOT EXISTS category_edges (
    parent_category TEXT NOT NULL,
    child_category TEXT NOT NULL,
    PRIMARY KEY (parent_category, child_category)
);

CREATE TABLE IF NOT EXISTS domain_decisions (
    domain_hash TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    category TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence REAL,
    reason TEXT,
    root TEXT,
    depth INTEGER,
    source TEXT NOT NULL,
    decision_at TEXT NOT NULL,
    PRIMARY KEY (domain_hash, source_fingerprint, category)
);

-- Indexes for high-throughput query performance
CREATE INDEX IF NOT EXISTS idx_category_edges_parent ON category_edges(parent_category);
CREATE INDEX IF NOT EXISTS idx_category_membership_cat ON category_membership(category);
CREATE INDEX IF NOT EXISTS idx_category_membership_page ON category_membership(page_id);
CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title);
CREATE INDEX IF NOT EXISTS idx_categories_cat ON categories(category);
CREATE INDEX IF NOT EXISTS idx_categories_nocase ON categories(category COLLATE NOCASE);
