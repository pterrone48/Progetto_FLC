"""
Competency Questions Module

Executes SPARQL queries against the inferred knowledge base to validate 
that the ontology can answer domain-specific questions. Queries are organized 
by type: Descriptive, Analytical, and Structural.

The module distinguishes between executed queries and informative queries 
(those returning meaningful results), providing detailed feedback on coverage.
"""

import rdflib
import time
from typing import Dict, Tuple


def get_queries() -> Dict[str, Tuple[str, str]]:
    """
    Return dictionary of competency questions organized by type.
    
    Returns:
        Dict mapping query ID to (description, SPARQL query) tuples
    """
    prefixes = """
        PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
        PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    """

    queries = {
        "CQ1_Descriptive": ("Extraction of Incidents-Dates-Actors", """
            SELECT ?incidente ?data ?tipoAttore WHERE {
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
              OPTIONAL {
                { ?incidente slash:hasActorType ?tipoAttore }
                UNION { ?incidente hash:hasActorType ?tipoAttore }
              }
            } LIMIT 50
        """),
        
        "CQ2_Analytical": ("Quantitative Analysis by Actor Type", """
            SELECT ?tipoAttore (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasActorType ?tipoAttore } UNION { ?inc hash:hasActorType ?tipoAttore }
            } GROUP BY ?tipoAttore ORDER BY DESC(?n)
        """),
        
        "CQ3_Descriptive": ("Correlation between Type and Date", """
            SELECT ?incidente ?tipo ?data WHERE {
              { ?incidente slash:hasEventType ?tipo } UNION { ?incidente hash:hasEventType ?tipo }
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
            } LIMIT 20
        """),
        
        "CQ4_Descriptive": ("Organization-Industry Mapping", """
            SELECT ?org ?ind WHERE {
              { ?inc slash:hasOrganization ?org } UNION { ?inc hash:hasOrganization ?org }
              { ?inc slash:hasIndustry ?ind } UNION { ?inc hash:hasIndustry ?ind }
            } LIMIT 20
        """),
        
        "CQ5_Analytical": ("Industry Ranking by Volume", """
            SELECT ?industria (COUNT(?incidente) AS ?totale) WHERE {
              { ?incidente slash:hasIndustry ?industria } UNION { ?incidente hash:hasIndustry ?industria }
            } GROUP BY ?industria ORDER BY DESC(?totale)
        """),
        
        "CQ6_Analytical": ("Temporal Analysis Post-2020", """
            SELECT ?incidente ?data WHERE {
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
              FILTER(?data > "2020-01-01T00:00:00"^^xsd:dateTime)
            } ORDER BY ?data LIMIT 20
        """),
        
        "CQ7_Analytical": ("Subtype Distribution by Industry", """
            SELECT ?industria ?sottotipo (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasIndustry ?industria } UNION { ?inc hash:hasIndustry ?industria }
              { ?inc slash:hasEventSubtype ?sottotipo } UNION { ?inc hash:hasEventSubtype ?sottotipo }
            } GROUP BY ?industria ?sottotipo ORDER BY ?industria DESC(?n)
        """),
        
        "CQ8_Structural": ("TBox Evolution - New Classes", """
            SELECT ?classe ?super WHERE {
              ?classe rdfs:subClassOf ?super .
              FILTER(isIRI(?classe) && !strstarts(str(?classe), "http://www.w3.org"))
            } LIMIT 20
        """),
        
        "CQ9_Analytical": ("Detection of Incomplete Records", """
            SELECT (COUNT(DISTINCT ?inc) AS ?incompleti) WHERE {
              { ?inc slash:hasEventDate ?d } UNION { ?inc hash:hasEventDate ?d }
              FILTER NOT EXISTS {
                { ?inc slash:hasOrganization ?o } UNION { ?inc hash:hasOrganization ?o }
              }
            }
        """),
        
        "CQ10_Structural": ("Validation of isType_of Relations", """
            SELECT ?incidente ?tipo WHERE {
              { ?incidente slash:isType_of ?tipo } UNION { ?incidente hash:isType_of ?tipo }
            } LIMIT 20
        """),
        
        "CQ11_Analytical": ("Monthly Attack Trends", """
            SELECT ?mese (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasMonth ?mese } UNION { ?inc hash:hasMonth ?mese }
            } GROUP BY ?mese ORDER BY ?mese
        """),
        
        "CQ12_Analytical": ("Geographic Distribution of Incidents", """
            SELECT ?paese (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasCountry ?paese } UNION { ?inc hash:hasCountry ?paese }
            } GROUP BY ?paese ORDER BY DESC(?n)
        """),
        
        "CQ13_Analytical": ("Actor-Attack Type Correlation", """
            SELECT ?tipoAttore ?tipoAttacco (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasActorType ?tipoAttore } UNION { ?inc hash:hasActorType ?tipoAttore }
              { ?inc slash:hasEventType ?tipoAttacco } UNION { ?inc hash:hasEventType ?tipoAttacco }
            } GROUP BY ?tipoAttore ?tipoAttacco ORDER BY DESC(?n)
        """),
        
        "CQ14_Structural": ("Detection of Empty Subclasses", """
            SELECT ?classe WHERE {
              ?classe a owl:Class .
              FILTER NOT EXISTS { ?i a ?classe }
              FILTER(isIRI(?classe) && !strstarts(str(?classe), "http://www.w3.org"))
            }
        """),
        
        "CQ15_Analytical": ("Analysis of Prevalent Motivations", """
            SELECT ?sottotipo (COUNT(?inc) AS ?tot) WHERE {
              { ?inc slash:hasEventSubtype ?sottotipo } UNION { ?inc hash:hasEventSubtype ?sottotipo }
            } GROUP BY ?sottotipo ORDER BY DESC(?tot)
        """),
        
        "CQ16_Structural": ("Chain Actor-Incident-Type", """
            SELECT ?tipoAttore ?incidente ?tipoAttacco ?industria WHERE {
              { ?incidente slash:hasActorType ?tipoAttore } UNION { ?incidente hash:hasActorType ?tipoAttore }
              { ?incidente slash:hasEventType ?tipoAttacco } UNION { ?incidente hash:hasEventType ?tipoAttacco }
              { ?incidente slash:hasIndustry ?industria } UNION { ?incidente hash:hasIndustry ?industria }
            } LIMIT 20
        """),
        
        "CQ17_Structural": ("Individuals with Multiple Attributes", """
            SELECT ?inc (COUNT(DISTINCT ?p) AS ?nProp) WHERE {
              { ?inc slash:hasEventDate ?d } UNION { ?inc hash:hasEventDate ?d }
              ?inc ?p ?v .
              FILTER(isLiteral(?v))
            } GROUP BY ?inc HAVING (?nProp >= 4) ORDER BY DESC(?nProp) LIMIT 20
        """),
        
        "CQ18_Analytical": ("Behaviour Analysis by Industry", """
            SELECT ?industria ?beh (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasIndustry ?industria } UNION { ?inc hash:hasIndustry ?industria }
              { ?inc slash:behaviour ?beh } UNION { ?inc hash:behaviour ?beh }
            } GROUP BY ?industria ?beh ORDER BY ?industria DESC(?n)
        """),
        
        "CQ19_Analytical": ("Behaviour vs Type Correlation", """
            SELECT ?beh ?tipo (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:behaviour ?beh } UNION { ?inc hash:behaviour ?beh }
              { ?inc slash:hasEventType ?tipo } UNION { ?inc hash:hasEventType ?tipo }
            } GROUP BY ?beh ?tipo ORDER BY ?beh DESC(?n)
        """),
        
        "CQ20_Structural": ("Individuals per Parent Class", """
            SELECT ?super (COUNT(?i) AS ?n) WHERE {
              ?i a ?classe .
              ?classe rdfs:subClassOf ?super .
            } GROUP BY ?super ORDER BY DESC(?n) LIMIT 20
        """),
        
        "CQ21_Comparative": ("New Classes from Inference", """
            SELECT DISTINCT ?newClass WHERE {
              ?newClass a owl:Class .
              ?newClass rdfs:subClassOf* ?parent .
              FILTER(!strstarts(str(?newClass), "http://www.w3.org"))
            } LIMIT 30
        """),
        
        "CQ22_Comparative": ("Property Coverage Analysis", """
            SELECT ?prop (COUNT(?s) AS ?usage) WHERE {
              ?s ?prop ?o .
              FILTER(?prop != rdf:type)
            } GROUP BY ?prop ORDER BY DESC(?usage) LIMIT 20
        """)
    }
    
    return {qid: (prefixes + sparql, desc) for qid, (desc, sparql) in queries.items()}


def run_competency_queries(onto_path: str, output_file: str) -> Tuple[int, int]:
    """
    Execute all competency queries and write results to file.
    
    Args:
        onto_path: Path to the ontology file in Turtle format
        output_file: Path to output results file
        
    Returns:
        Tuple of (executed_count, informative_count)
    """
    g = rdflib.Graph()
    g.parse(onto_path, format="turtle")
    
    queries = get_queries()
    
    executed_count = 0
    informative_count = 0
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("COMPETENCY QUESTIONS REPORT\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Ontology: {onto_path}\n")
        f.write(f"Total triples: {len(g)}\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("QUERY CLASSIFICATION SUMMARY\n")
        f.write("=" * 60 + "\n")
        
        descriptive = sum(1 for qid in queries if "_Descriptive" in qid)
        analytical = sum(1 for qid in queries if "_Analytical" in qid)
        structural = sum(1 for qid in queries if "_Structural" in qid)
        comparative = sum(1 for qid in queries if "_Comparative" in qid)
        
        f.write(f"Descriptive Queries: {descriptive}\n")
        f.write(f"Analytical Queries: {analytical}\n")
        f.write(f"Structural Queries: {structural}\n")
        f.write(f"Comparative Queries: {comparative}\n")
        f.write(f"Total Queries: {len(queries)}\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("DETAILED RESULTS\n")
        f.write("=" * 60 + "\n\n")
        
        for qid, (sparql, description) in queries.items():
            f.write(f"QUERY: {qid} - {description}\n")
            f.write("-" * 50 + "\n")
            
            try:
                results = g.query(sparql)
                executed_count += 1
                
                if len(results) == 0:
                    f.write("Status: EXECUTED (No results returned)\n")
                else:
                    informative_count += 1
                    f.write(f"Status: INFORMATIVE ({len(results)} results)\n\n")
                    
                    vars_list = [str(v) for v in results.vars]
                    f.write(" | ".join(vars_list) + "\n")
                    
                    for i, row in enumerate(results):
                        if i >= 10:
                            f.write(f"... and {len(results) - 10} more rows\n")
                            break
                        line = [str(val).split('/')[-1].split('#')[-1] if val is not None else "None" for val in row]
                        f.write(" | ".join(line) + "\n")
                        
            except Exception as e:
                f.write(f"Status: ERROR - {e}\n")
            
            f.write("\n" + "=" * 50 + "\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 60 + "\n")
        f.write(f"Queries Executed: {executed_count}/{len(queries)}\n")
        f.write(f"Informative Queries: {informative_count}/{len(queries)}\n")
        f.write(f"Coverage: {round(informative_count/len(queries)*100, 1) if queries else 0}%\n")
    
    return executed_count, informative_count


if __name__ == "__main__":
    run_competency_queries("UCO_INFERRED.ttl", "RISULTATI_QUERY_CQ.txt")
