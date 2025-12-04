
// Neo4j V4 Import Script
// 建议使用 cypher-shell 运行: cat import_script.cypher | cypher-shell -u neo4j -p password
// 或者在 Neo4j Browser 中直接运行。注意：需确保 neo4j 配置了 dbms.security.allow_csv_import_from_file_urls=true

// 1. Indices
CREATE CONSTRAINT IF NOT EXISTS ON (n:E27_Site) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E53_Place) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E25_Man_Made_Feature) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E22_Man_Made_Object) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E4_Period) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E12_Production) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E55_Type) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS ON (n:E57_Material) ASSERT n.id IS UNIQUE;

// 2. Nodes
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_site.csv' AS row MERGE (n:E27_Site {id: row.id}) SET n.name=row.name, n.location=row.location;
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_place.csv' AS row MERGE (n:E53_Place {id: row.id}) SET n.name=row.name, n.type=row.type;
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_feature.csv' AS row MERGE (n:E25_Man_Made_Feature {id: row.id}) SET n.name=row.name, n.code=row.code, n.type=row.type;
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_period.csv' AS row MERGE (n:E4_Period {id: row.id}) SET n.name=row.name, n.start_date=row.start_date;
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_artifact.csv' AS row MERGE (n:E22_Man_Made_Object {id: row.id}) SET n.name=row.name, n.category=row.category, n.height=toFloat(row.height);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_production.csv' AS row MERGE (n:E12_Production {id: row.id}) SET n.note=row.note;
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_concept.csv' AS row CALL apoc.create.node([row.LABEL], {id: row.id, name: row.name}) YIELD node RETURN count(node);

// 3. Edges
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_spatial.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_period.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) MERGE (s)-[:P7_took_place_at]->(e);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_obj_loc.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) MERGE (s)-[:P53_has_former_or_current_location]->(e);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_obj_attr.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_prod_link.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) MERGE (s)-[:P108i_was_produced_by]->(e);
:auto LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_prod_attr.csv' AS row MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);

