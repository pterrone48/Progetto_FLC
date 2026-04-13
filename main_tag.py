import os
import sys
import time
import subprocess
import rdflib
from rdflib import RDF, RDFS, OWL, XSD, Literal, URIRef
from owlready2 import *
from tqdm import tqdm

try:
    from structural_validator import run_structural_check
    from competecy_questions import run_competency_queries
except ImportError:
    def run_structural_check(x): return []
    def run_competency_queries(x, y): pass

def setup_java():
    if sys.platform == "darwin":
        try:
            java_home = subprocess.check_output(['/usr/libexec/java_home']).decode().strip()
            owlready2.JAVA_EXE = os.path.join(java_home, "bin", "java")
        except:
            owlready2.JAVA_EXE = "java"
    else:
        owlready2.JAVA_EXE = "java"
    owlready2.reasoning.JAVA_MEMORY = 16000

def run_reasoning(onto):
    with onto:
        sync_reasoner_pellet(
            infer_property_values=True,
            infer_data_property_values=True,
            debug=0
        )

def main():
    setup_java()
    start_time = time.time()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    xml_file = os.path.join(base_dir, "UCO_FINAL_COMP.xml")
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
        run_reasoning(onto)
        inference_status = "Consistent"
    except Exception as e:
        inference_status = f"Inconsistent - {str(e)}"

    g_clean = rdflib.Graph()
    for s, p, o in tqdm(default_world.as_rdflib_graph(), desc="Exporting triples"):
        s_str, p_str, o_str = str(s), str(p), str(o)
        
        if "DATAPROPVAL" in s_str or "DATAPROPVAL" in p_str or "DATAPROPVAL" in o_str:
            continue
        
        if any(char in s_str for char in [' ', '{', '}']): continue
        if any(char in p_str for char in [' ', '{', '}']): continue
            
        g_clean.add((s, p, o))

    g_clean.serialize(destination=inferred_file, format="turtle")

    structural_issues = run_structural_check(xml_file)
    run_competency_queries(inferred_file, query_results)

    triples_inf = len(g_clean)
    n_classes = len(list(g_clean.subjects(RDF.type, OWL.Class)))
    n_individuals = len(list(g_clean.subjects(RDF.type, OWL.NamedIndividual)))
    n_properties = len(list(g_clean.subjects(RDF.type, OWL.ObjectProperty))) + \
                   len(list(g_clean.subjects(RDF.type, OWL.DatatypeProperty)))

    inf_gain = triples_inf - triples_raw
    gain_pct = round((inf_gain / triples_raw) * 100, 2) if triples_raw else 0

    hierarchical_depth = 0
    classes_list = list(g_clean.subjects(RDF.type, OWL.Class))
    for cls in tqdm(classes_list, desc="Calculating Metrics"):
        depth = len(list(g_clean.transitive_objects(cls, RDFS.subClassOf)))
        hierarchical_depth = max(hierarchical_depth, depth)

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("REPORT TECNICO\n\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Esito: {inference_status}\n")
        f.write(f"Durata: {round(time.time() - start_time, 2)}s\n\n")
        f.write(f"Triple base: {triples_raw}\n")
        f.write(f"Triple inferite (pulite): {triples_inf}\n")
        f.write(f"Expansion: {gain_pct}%\n\n")
        f.write(f"Classi: {n_classes}\n")
        f.write(f"Individui: {n_individuals}\n")
        f.write(f"Proprietà: {n_properties}\n")
        f.write(f"Depth: {hierarchical_depth}\n")

if __name__ == "__main__":
    main()