from neo4j import GraphDatabase

uri = "bolt+s://f6b8bf67.databases.neo4j.io:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j","PASSWORD"), encrypted=True)

with driver.session(database="neo4j") as s:
    result = s.run("RETURN 1 AS ok")
    print(result.single()["ok"])
