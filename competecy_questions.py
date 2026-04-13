import rdflib
import time

def run_competency_queries(onto_path, output_file):
    g = rdflib.Graph()
    g.parse(onto_path, format="turtle")

    prefixes = """
        PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
        PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    """

    queries = {
        "1. Estrazione Incidenti-Date-Attori": """
            SELECT ?incidente ?data ?tipoAttore WHERE {
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
              OPTIONAL {
                { ?incidente slash:hasActorType ?tipoAttore }
                UNION { ?incidente hash:hasActorType ?tipoAttore }
              }
            } LIMIT 50
        """,
        "2. Analisi quantitativa per Attore": """
            SELECT ?tipoAttore (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasActorType ?tipoAttore } UNION { ?inc hash:hasActorType ?tipoAttore }
            } GROUP BY ?tipoAttore ORDER BY DESC(?n)
        """,
        "3. Correlazione Tipo-Data": """
            SELECT ?incidente ?tipo ?data WHERE {
              { ?incidente slash:hasEventType ?tipo } UNION { ?incidente hash:hasEventType ?tipo }
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
            } LIMIT 20
        """,
        "4. Mapping Organizzazione-Industria": """
            SELECT ?org ?ind WHERE {
              { ?inc slash:hasOrganization ?org } UNION { ?inc hash:hasOrganization ?org }
              { ?inc slash:hasIndustry ?ind } UNION { ?inc hash:hasIndustry ?ind }
            } LIMIT 20
        """,
        "5. Classifica Settori per Volume": """
            SELECT ?industria (COUNT(?incidente) AS ?totale) WHERE {
              { ?incidente slash:hasIndustry ?industria } UNION { ?incidente hash:hasIndustry ?industria }
            } GROUP BY ?industria ORDER BY DESC(?totale)
        """,
        "6. Analisi Temporale post-2020": """
            SELECT ?incidente ?data WHERE {
              { ?incidente slash:hasEventDate ?data } UNION { ?incidente hash:hasEventDate ?data }
              FILTER(?data > "2020-01-01T00:00:00"^^xsd:dateTime)
            } ORDER BY ?data LIMIT 20
        """,
        "7. Distribuzione Sottotipi per Settore": """
            SELECT ?industria ?sottotipo (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasIndustry ?industria } UNION { ?inc hash:hasIndustry ?industria }
              { ?inc slash:hasEventSubtype ?sottotipo } UNION { ?inc hash:hasEventSubtype ?sottotipo }
            } GROUP BY ?industria ?sottotipo ORDER BY ?industria DESC(?n)
        """,
        "8. Evoluzione TBox (Nuove Classi)": """
            SELECT ?classe ?super WHERE {
              ?classe rdfs:subClassOf ?super .
              FILTER(isIRI(?classe) && !strstarts(str(?classe), "http://www.w3.org"))
            } LIMIT 20
        """,
        "9. Rilevamento Record Incompleti": """
            SELECT (COUNT(DISTINCT ?inc) AS ?incompleti) WHERE {
              { ?inc slash:hasEventDate ?d } UNION { ?inc hash:hasEventDate ?d }
              FILTER NOT EXISTS {
                { ?inc slash:hasOrganization ?o } UNION { ?inc hash:hasOrganization ?o }
              }
            }
        """,
        "10. Validazione Relazioni isType_of": """
            SELECT ?incidente ?tipo WHERE {
              { ?incidente slash:isType_of ?tipo } UNION { ?incidente hash:isType_of ?tipo }
            } LIMIT 20
        """,
        "11. Trend Mensile degli Attacchi": """
            SELECT ?mese (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasMonth ?mese } UNION { ?inc hash:hasMonth ?mese }
            } GROUP BY ?mese ORDER BY ?mese
        """,
        "12. Analisi Geografica degli Incidenti": """
            SELECT ?paese (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasCountry ?paese } UNION { ?inc hash:hasCountry ?paese }
            } GROUP BY ?paese ORDER BY DESC(?n)
        """,
        "13. Correlazione Attore-Tipo Attacco": """
            SELECT ?tipoAttore ?tipoAttacco (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasActorType ?tipoAttore } UNION { ?inc hash:hasActorType ?tipoAttore }
              { ?inc slash:hasEventType ?tipoAttacco } UNION { ?inc hash:hasEventType ?tipoAttacco }
            } GROUP BY ?tipoAttore ?tipoAttacco ORDER BY DESC(?n)
        """,
        "14. Rilevamento Sottoclassi Senza Istanze": """
            SELECT ?classe WHERE {
              ?classe a owl:Class .
              FILTER NOT EXISTS { ?i a ?classe }
              FILTER(isIRI(?classe) && !strstarts(str(?classe), "http://www.w3.org"))
            }
        """,
        "15. Analisi delle Motivazioni prevalenti": """
            SELECT ?sottotipo (COUNT(?inc) AS ?tot) WHERE {
              { ?inc slash:hasEventSubtype ?sottotipo } UNION { ?inc hash:hasEventSubtype ?sottotipo }
            } GROUP BY ?sottotipo ORDER BY DESC(?tot)
        """,
        "16. Catena Attore -> Incidente -> Tipo": """
            SELECT ?tipoAttore ?incidente ?tipoAttacco ?industria WHERE {
              { ?incidente slash:hasActorType ?tipoAttore } UNION { ?incidente hash:hasActorType ?tipoAttore }
              { ?incidente slash:hasEventType ?tipoAttacco } UNION { ?incidente hash:hasEventType ?tipoAttacco }
              { ?incidente slash:hasIndustry ?industria } UNION { ?incidente hash:hasIndustry ?industria }
            } LIMIT 20
        """,
        "17. Identificazione Individui con Attributi Multipli": """
            SELECT ?inc (COUNT(DISTINCT ?p) AS ?nProp) WHERE {
              { ?inc slash:hasEventDate ?d } UNION { ?inc hash:hasEventDate ?d }
              ?inc ?p ?v .
              FILTER(isLiteral(?v))
            } GROUP BY ?inc HAVING (?nProp >= 4) ORDER BY DESC(?nProp) LIMIT 20
        """,
        "18. Analisi Behaviour per Settore": """
            SELECT ?industria ?beh (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:hasIndustry ?industria } UNION { ?inc hash:hasIndustry ?industria }
              { ?inc slash:behaviour ?beh } UNION { ?inc hash:behaviour ?beh }
            } GROUP BY ?industria ?beh ORDER BY ?industria DESC(?n)
        """,
        "19. Behaviour vs Tipo": """
            SELECT ?beh ?tipo (COUNT(?inc) AS ?n) WHERE {
              { ?inc slash:behaviour ?beh } UNION { ?inc hash:behaviour ?beh }
              { ?inc slash:hasEventType ?tipo } UNION { ?inc hash:hasEventType ?tipo }
            } GROUP BY ?beh ?tipo ORDER BY ?beh DESC(?n)
        """,
        "20. Individui per Classe Madre": """
            SELECT ?super (COUNT(?i) AS ?n) WHERE {
              ?i a ?classe .
              ?classe rdfs:subClassOf ?super .
            } GROUP BY ?super ORDER BY DESC(?n) LIMIT 20
        """
    }

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("COMPETENCY QUESTIONS REPORT\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for title, sparql in queries.items():
            f.write(f"QUERY: {title}\n")
            try:
                results = g.query(prefixes + sparql)
                if len(results) == 0:
                    f.write("Nessun dato rilevato\n")
                else:
                    vars_list = [str(v) for v in results.vars]
                    f.write(" | ".join(vars_list) + "\n")
                    for row in results:
                        line = [str(val).split('/')[-1].split('#')[-1] if val is not None else "None"
                                for val in row]
                        f.write(" | ".join(line) + "\n")
            except Exception as e:
                f.write(f"Errore: {e}\n")
            f.write("\n" + "-"*50 + "\n\n")