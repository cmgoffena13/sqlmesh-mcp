PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS watermarks (
    id                  INTEGER NOT NULL PRIMARY KEY CHECK (id = 1),
    last_full_parse     INTEGER NOT NULL DEFAULT 0,
    last_incremental    INTEGER DEFAULT 0
);
INSERT OR IGNORE INTO watermarks (id, last_full_parse, last_incremental) VALUES (1, 0, 0);

CREATE TABLE IF NOT EXISTS index_root (
    id      INTEGER NOT NULL PRIMARY KEY CHECK (id = 1),
    path    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS directories (
    id              INTEGER NOT NULL PRIMARY KEY,
    parent_id       INTEGER REFERENCES directories(id),  
    name            TEXT NOT NULL,                     
    path            TEXT UNIQUE NOT NULL,               
    depth           INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id              INTEGER NOT NULL PRIMARY KEY,
    directory_id    INTEGER REFERENCES directories(id),
    name            TEXT NOT NULL,                       
    path            TEXT UNIQUE NOT NULL,   
    normalized_path TEXT NOT NULL,             
    language        TEXT,                                          
    content_hash    TEXT NOT NULL,                               
    line_count      INTEGER NOT NULL DEFAULT 0,
    symbol_count    INTEGER NOT NULL DEFAULT 0,
    is_test         BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS files_normalized_path_index ON files (normalized_path);

CREATE TABLE IF NOT EXISTS symbols (
    id              INTEGER NOT NULL PRIMARY KEY,
    file_id         INTEGER REFERENCES files(id),
    parent_id       INTEGER REFERENCES symbols(id),
    name            TEXT NOT NULL,
    qualified_name  TEXT NOT NULL,
    kind            TEXT NOT NULL, /* model, external_model, cte, macro, column */
    line_start      INTEGER NOT NULL,
    line_end        INTEGER NOT NULL,
    line_count      INTEGER NOT NULL,
    data_type       TEXT,
    position_index  INTEGER,
    docstring       TEXT, /* model description, column description, macro description */
    language        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS symbols_file_id_index ON symbols (file_id);
CREATE UNIQUE INDEX IF NOT EXISTS symbols_qualified_name_index ON symbols (qualified_name);