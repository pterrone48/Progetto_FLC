import rdflib
import time
import os

def run_competency_queries(onto_path, output_file):
    g = rdflib.Graph()
    
    g.parse(onto_path, format="turtle")
    
    queries = {
        "1. Estrazione base Incidenti-Date-Attori": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?incidente ?data ?attore WHERE {
              ?incidente slash:hasEventDate ?data .
              OPTIONAL { ?incidente hash:isLaunchedBy ?attore . }
            } LIMIT 25
        """,
        "2. Analisi quantitativa per Attore": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            SELECT ?attore (COUNT(?incidente) AS ?numeroAttacchi) WHERE {
              ?incidente hash:isLaunchedBy ?attore .
            } GROUP BY ?attore ORDER BY DESC(?numeroAttacchi)
        """,
        "3. Correlazione Tipo-Data": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?incidente ?tipoEvento ?data WHERE {
              ?incidente slash:hasEventType ?tipoEvento .
              ?incidente slash:hasEventDate ?data .
            } LIMIT 20
        """,
        "4. Mapping Organizzazione-Industria": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?organizzazione ?industria ?incidente WHERE {
              ?incidente slash:hasOrganization ?organizzazione .
              ?incidente slash:hasIndustry ?industria .
            }
        """,
        "5. Classifica Settori per Volume": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?industria (COUNT(?incidente) AS ?totale) WHERE {
              ?incidente slash:hasIndustry ?industria .
            } GROUP BY ?industria ORDER BY DESC(?totale)
        """,
        "6. Analisi Temporale post-2020": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            SELECT ?incidente ?data ?tipo WHERE {
              ?incidente slash:hasEventDate ?data .
              ?incidente slash:hasEventType ?tipo .
              FILTER(xsd:dateTime(?data) > "2020-01-01T00:00:00"^^xsd:dateTime)
            } ORDER BY ?data
        """,
        "7. Analisi Cross-Relazionale (Campagna-Vittima-Tipo)": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?campagna ?vittima ?tipo WHERE {
              ?incidente hash:associatedCampaigns ?campagna .
              ?incidente slash:hasOrganization ?vittima .
              ?incidente slash:hasEventType ?tipo .
            }
        """,
        "8. Identificazione di Nuove Classi (Evoluzione TBox)": """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?nuovaClasse ?superClasse WHERE {
              ?nuovaClasse rdfs:subClassOf ?superClasse .
              FILTER(isIRI(?nuovaClasse) && !strstarts(str(?nuovaClasse), "http://www.w3.org"))
            }
        """,
        "9. Rilevamento Record Incompleti (Data Quality)": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?incidente WHERE {
              ?incidente a ?tipo .
              FILTER NOT EXISTS { ?incidente slash:hasOrganization ?o }
            } LIMIT 10
        """,
        "10. Validazione Relazioni Inverse Inferite": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?soggetto ?oggetto WHERE {
              ?soggetto <http://ffrdc.ebiquity.umbc.edu/ns/ontology/isAssociatedCampaign_of> ?oggetto .
            }
        """,
        "11. Distribuzione Mensile degli Attacchi (Trend)": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?mese (COUNT(?incidente) AS ?conteggio) WHERE {
              ?incidente slash:hasMonth ?mese .
            } GROUP BY ?mese ORDER BY ?mese
        """,
        "12. Analisi Geografica degli Incidenti": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?paese (COUNT(?incidente) AS ?totale) WHERE {
              ?incidente slash:hasCountry ?paese .
            } GROUP BY ?paese ORDER BY DESC(?totale)
        """,
        "13. Correlazione Attore-Tipo Attacco (Specializzazione)": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?attore ?tipo (COUNT(?incidente) AS ?n) WHERE {
              ?incidente hash:isLaunchedBy ?attore .
              ?incidente slash:hasEventType ?tipo .
            } GROUP BY ?attore ?tipo HAVING (?n > 1)
        """,
        "14. Rilevamento Sottoclassi Senza Istanze (Dead Classes)": """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?classe WHERE {
              ?classe a owl:Class .
              FILTER NOT EXISTS { ?i a ?classe }
              FILTER(isIRI(?classe) && !strstarts(str(?classe), "http://www.w3.org"))
            }
        """,
        "15. Analisi delle Motivazioni prevalenti": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?motivo (COUNT(?incidente) AS ?tot) WHERE {
              ?incidente slash:hasMotive ?motivo .
            } GROUP BY ?motivo ORDER BY DESC(?tot)
        """,
        "16. Catena di Relazioni (Attore -> Incidente -> Campagna)": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            SELECT ?attore ?incidente ?campagna WHERE {
              ?incidente hash:isLaunchedBy ?attore .
              ?incidente hash:associatedCampaigns ?campagna .
            }
        """,
        "17. Identificazione Individui con Commenti Multipli (Anomalie)": """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?s (COUNT(?c) AS ?n) WHERE {
              ?s rdfs:comment ?c .
            } GROUP BY ?s HAVING (?n > 1)
        """,
        "18. Analisi delle Campagne per Settore Industriale": """
            PREFIX hash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology#>
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?campagna ?industria (COUNT(?incidente) AS ?n) WHERE {
              ?incidente hash:associatedCampaigns ?campagna .
              ?incidente slash:hasIndustry ?industria .
            } GROUP BY ?campagna ?industria
        """,
        "19. Filtro Comportamentale (Behaviour vs Tipo)": """
            PREFIX slash: <http://ffrdc.ebiquity.umbc.edu/ns/ontology/>
            SELECT ?behaviour ?tipo (COUNT(?incidente) AS ?n) WHERE {
              ?incidente slash:behaviour ?behaviour .
              ?incidente slash:hasEventType ?tipo .
            } GROUP BY ?behaviour ?tipo
        """,
        "20. Statistiche di Inserimento (Individui per Classe Madre)": """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?superClasse (COUNT(?i) AS ?nIndividui) WHERE {
              ?i a ?classe .
              ?classe rdfs:subClassOf ?superClasse .
            } GROUP BY ?superClasse ORDER BY DESC(?nIndividui)
        """
    }

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("COMPETENCY QUESTIONS REPORT\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for title, sparql in queries.items():
            f.write(f"QUERY: {title}\n")
            try:
                results = g.query(sparql)
                if len(results) == 0:
                    f.write("Nessun dato rilevato\n")
                else:
                    vars_list = [str(v) for v in results.vars]
                    f.write(" | ".join(vars_list) + "\n")
                    for row in results:
                        line = [str(val).split('/')[-1].split('#')[-1] for val in row]
                        f.write(" | ".join(line) + "\n")
            except Exception as e:
                f.write(f"Errore: {e}\n")
            f.write("\n" + "-"*50 + "\n\n")