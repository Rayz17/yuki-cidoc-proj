// Neo4j V4 Import Script
// 建议使用 cypher-shell 运行: cat import_script.cypher | cypher-shell -u neo4j -p password
// 或者在 Neo4j Browser 中直接运行。注意：需确保 neo4j 配置了 dbms.security.allow_csv_import_from_file_urls=true

// 1. Indices (Added generic Entity index for performance)
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E27_Site) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E53_Place) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E25_Man_Made_Feature) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E22_Man_Made_Object) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E4_Period) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E12_Production) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E55_Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E57_Material) REQUIRE n.id IS UNIQUE;
// 全局索引，用于关系导入加速
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;

// 2. Nodes (Adding :Entity label to all nodes)
// 请逐条运行
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_site.csv' AS row MERGE (n:E27_Site {id: row.id}) SET n:Entity, n.name=row.name, n.location=row.location;
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_place.csv' AS row MERGE (n:E53_Place {id: row.id}) SET n:Entity, n.name=row.name, n.type=row.type;
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_feature.csv' AS row MERGE (n:E25_Man_Made_Feature {id: row.id}) SET n:Entity, n.name=row.name, n.code=row.code, n.type=row.type;
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_period.csv' AS row MERGE (n:E4_Period {id: row.id}) SET n:Entity, n.name=row.name, n.start_date=row.start_date;
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_artifact.csv' AS row MERGE (n:E22_Man_Made_Object {id: row.id}) SET n:Entity, n.name=row.name, n.category=row.category, n.height=toFloat(row.height);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_production.csv' AS row MERGE (n:E12_Production {id: row.id}) SET n:Entity, n.note=row.note;
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/nodes_concept.csv' AS row CALL apoc.create.node([row.LABEL, 'Entity'], {id: row.id, name: row.name}) YIELD node RETURN count(node);

// 3. Edges (Using :Entity index for matching)
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_spatial.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_period.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) MERGE (s)-[:P7_took_place_at]->(e);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_obj_loc.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) MERGE (s)-[:P53_has_former_or_current_location]->(e);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_obj_attr.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_prod_link.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) MERGE (s)-[:P108i_was_produced_by]->(e);
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4/edges_prod_attr.csv' AS row MATCH (s:Entity {id: row.START_ID}) MATCH (e:Entity {id: row.END_ID}) CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);
