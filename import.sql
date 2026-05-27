-- Clear any existing tables
DROP TABLE IF EXISTS rooms;
DROP TABLE IF EXISTS gifts;
DROP TABLE IF EXISTS comments;

-- Import rooms table
CREATE TABLE rooms AS SELECT * FROM read_csv('rooms.tsv', 
    delim='\t', 
    header=true, 
    nullstr='NULL'
);

-- Import gifts table
CREATE TABLE gifts AS SELECT * FROM read_csv('gifts.tsv', 
    delim='\t', 
    header=true, 
    nullstr='NULL'
);

-- Import comments table
CREATE TABLE comments AS SELECT * FROM read_csv('comments.tsv', 
    delim='\t', 
    header=true, 
    nullstr='NULL'
);

-- Output basic ingestion status
SELECT 'rooms' AS table_name, count(*) AS row_count FROM rooms
UNION ALL
SELECT 'gifts' AS table_name, count(*) AS row_count FROM gifts
UNION ALL
SELECT 'comments' AS table_name, count(*) AS row_count FROM comments;
