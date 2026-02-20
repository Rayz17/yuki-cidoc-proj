
// V5 Import Script (CIDOC + Feature Units)

// 1. 约束
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E27_Site) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E53_Place) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E25_Man_Made_Feature) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E22_Man_Made_Object) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E4_Period) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E12_Production) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E55_Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E57_Material) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureUnit) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureMetric) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureValue) REQUIRE n.id IS UNIQUE;

// 2. 节点
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_site.csv' AS row
MERGE (n:E27_Site {id: row.id})
SET n.name = row.name, n.location = row.location;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_place.csv' AS row
MERGE (n:E53_Place {id: row.id})
SET n.name = row.name, n.type = row.type;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_feature.csv' AS row
MERGE (n:E25_Man_Made_Feature {id: row.id})
SET n.name = row.name, n.code = row.code, n.type = row.type;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_period.csv' AS row
MERGE (n:E4_Period {id: row.id})
SET n.name = row.name, n.start_date = row.start_date, n.end_date = row.end_date;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_artifact.csv' AS row
MERGE (n:E22_Man_Made_Object {id: row.id})
SET n.name = row.name, n.category = row.category, n.height = toFloat(row.height);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_production.csv' AS row
MERGE (n:E12_Production {id: row.id})
SET n.note = row.note;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_concept.csv' AS row
CALL apoc.create.node([row.LABEL], {id: row.id, name: row.name}) YIELD node
RETURN count(node);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_feature_units.csv' AS row
MERGE (u:FeatureUnit {id: row.id})
SET u.name = row.name,
    u.domain = row.domain,
    u.cidoc_domain = row.cidoc_domain,
    u.cidoc_property = row.cidoc_property,
    u.cidoc_intermediate = row.cidoc_intermediate,
    u.cidoc_range = row.cidoc_range;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_feature_metrics.csv' AS row
MERGE (m:FeatureMetric {id: row.id})
SET m.name = row.name;

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/nodes_feature_values.csv' AS row
MERGE (v:FeatureValue {id: row.id})
SET v.raw = row.raw,
    v.numeric = toFloat(row.numeric),
    v.unit = row.unit;

// 3. 关系
LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_spatial.csv' AS row
MATCH (s {id: row.START_ID}) MATCH (e {id: row.END_ID})
CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_period.csv' AS row
MATCH (s:E4_Period {id: row.START_ID}) MATCH (e:E27_Site {id: row.END_ID})
MERGE (s)-[:P7_took_place_at]->(e);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_obj_loc.csv' AS row
MATCH (s:E22_Man_Made_Object {id: row.START_ID}) MATCH (e:E25_Man_Made_Feature {id: row.END_ID})
MERGE (s)-[:P53_has_former_or_current_location]->(e);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_obj_attr.csv' AS row
MATCH (s:E22_Man_Made_Object {id: row.START_ID}) MATCH (e {id: row.END_ID})
CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_prod_link.csv' AS row
MATCH (s:E22_Man_Made_Object {id: row.START_ID}) MATCH (e:E12_Production {id: row.END_ID})
MERGE (s)-[:P108i_was_produced_by]->(e);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_prod_attr.csv' AS row
MATCH (s:E12_Production {id: row.START_ID}) MATCH (e {id: row.END_ID})
CALL apoc.create.relationship(s, row.TYPE, {}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_feature_structure.csv' AS row
MATCH (m:FeatureMetric {id: row.START_ID}) MATCH (u:FeatureUnit {id: row.END_ID})
MERGE (m)-[:HAS_METRIC_OF]->(u);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_feature_links.csv' AS row
MATCH (s:E22_Man_Made_Object {id: row.START_ID}) MATCH (t {id: row.END_ID})
CALL apoc.create.relationship(s, row.TYPE, {}, t) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM 'https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5/edges_feature_values.csv' AS row
MATCH (s {id: row.START_ID}) MATCH (v:FeatureValue {id: row.END_ID})
MERGE (s)-[:HAS_VALUE]->(v);
