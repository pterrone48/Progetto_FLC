import os
import sys
import time
import subprocess
import rdflib
from owlready2 import *
from findcouples import OntologyEnricher
from addentities import enrich_tbox_rdflib
from kbonto import run_validated_injection
from structural_validator import run_structural_check
from competecy_questions import run_competency_queries

def install_requirements():
    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if os.path.exists(req_path):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        except:
            pass

def main():
    install_requirements()
    java_paths = [
        r"C:\Program Files (x86)\Common Files\Oracle\Java\java8path\java.exe",
        r"C:\Program Files\Common Files\Oracle\Java\javapath\java.exe",
        "java"
    ]
    for j in java_paths:
        if os.path.exists(j) or j == "java":
            owlready2.JAVA_EXE = j
            break

    start_time = time.time()
    inference_status = "Unknown"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.system(f"{sys.executable} cooccorrenze.py")
    os.system(f"{sys.executable} cooccorrenzeclassifier.py")
    
    enricher = OntologyEnricher()
    enricher.run("classifica_cooccorrenze.xlsx", "uco_1_5.ttl", "ontologyadd.xlsx")
    
    enrich_tbox_rdflib()
    run_validated_injection()

    xml_file = os.path.join(base_dir, "UCO_FINAL.xml")
    inferred_file = os.path.join(base_dir, "UCO_INFERRED.ttl")
    log_file = os.path.join(base_dir, "LOG_VALIDAZIONE.txt")
    query_results = os.path.join(base_dir, "RISULTATI_QUERY_CQ.txt")

    if not os.path.exists(xml_file):
        raise FileNotFoundError(xml_file)

    g_raw = rdflib.Graph()
    g_raw.parse(xml_file, format="xml")
    triples_raw = len(g_raw)

    onto = get_ontology(os.path.abspath(xml_file)).load()
    
    try:
        with onto:
            sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        inference_status = "Consistent"
        
        temp_nt = os.path.join(base_dir, "temp_inference.nt")
        onto.save(file=temp_nt, format="ntriples")
        
        g_inferred = rdflib.Graph()
        g_inferred.parse(temp_nt, format="nt")
        g_inferred.serialize(destination=inferred_file, format="turtle")
        
        if os.path.exists(temp_nt): os.remove(temp_nt)
        
    except Exception as e:
        inference_status = f"Error: {str(e)}"

    structural_issues = run_structural_check(xml_file)
    run_competency_queries(inferred_file, query_results)
    
    g_final = rdflib.Graph()
    g_final.parse(inferred_file, format="turtle")
    
    triples_inf = len(g_final)
    n_classes = len(list(g_final.subjects(rdflib.RDF.type, rdflib.OWL.Class)))
    n_individuals = len(list(g_final.subjects(rdflib.RDF.type, None))) - n_classes
    n_properties = len(list(g_final.subjects(rdflib.RDF.type, rdflib.OWL.ObjectProperty))) + \
                   len(list(g_final.subjects(rdflib.RDF.type, rdflib.OWL.DatatypeProperty)))
    
    inf_gain = triples_inf - triples_raw
    gain_pct = round((inf_gain / triples_raw) * 100, 2) if triples_raw > 0 else 0
    rel_density = round(triples_inf / n_individuals, 2) if n_individuals > 0 else 0
    connectivity_ratio = round(n_individuals / n_classes, 2) if n_classes > 0 else 0
    semantic_richness = round(n_properties / n_classes, 2) if n_classes > 0 else 0
    
    cq_count = 0
    if os.path.exists(query_results):
        with open(query_results, "r", encoding="utf-8") as qr:
            cq_count = qr.read().count("QUERY:")

    

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("REPORT TECNICO DI VALIDAZIONE E METRICHE\n\n")
        f.write(f"Timestamp esecuzione: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Esito coerenza logica: {inference_status}\n")
        f.write(f"Durata totale pipeline: {round(time.time() - start_time, 2)}s\n\n")
        
        f.write("VALUTAZIONE CRESCITA INFERENZIALE\n")
        f.write(f"Volume triple base: {triples_raw}\n")
        f.write(f"Volume triple inferite: {triples_inf}\n")
        f.write(f"Nuova conoscenza prodotta: {inf_gain} affermazioni\n")
        f.write(f"Coefficiente di espansione: {gain_pct}%\n\n")
        
        f.write("DESCRITTORI STRUTTURALI E COMPLESSITA\n")
        f.write(f"Classi totali: {n_classes}\n")
        f.write(f"Individui totali: {n_individuals}\n")
        f.write(f"Proprieta totali: {n_properties}\n")
        f.write(f"Rapporto istanze per classe: {connectivity_ratio}\n")
        f.write(f"Indice di ricchezza semantica: {semantic_richness}\n")
        f.write(f"Grado di densita relazionale: {rel_density}\n\n")
        
        f.write("EFFICACIA INFORMATIVA (COMPETENCY QUESTIONS)\n")
        f.write(f"Quesiti SPARQL risolti: {cq_count}/20\n\n")
        
        f.write("PITFALLS E ANOMALIE RILEVATE\n")
        if not structural_issues:
            f.write("Nessuna criticita strutturale.\n")
        else:
            for issue in structural_issues:
                f.write(f"{issue}\n")

if __name__ == "__main__":
    main()