import rdflib
from rdflib import RDF, RDFS, OWL
import os

def run_structural_check(file_path):
    g = rdflib.Graph()
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xml" or ext == ".owl":
        g.parse(file_path, format="xml")
    else:
        g.parse(file_path, format="turtle")
    
    issues = []
    
    for s in g.subjects(RDF.type, OWL.Class):
        if not list(g.objects(s, RDFS.comment)):
            issues.append(f"[P08] Missing comment for Class: {str(s).split('/')[-1].split('#')[-1]}")
            
    for s in g.subjects(RDF.type, None):
        if (s, RDF.type, OWL.Class) not in g and (s, RDF.type, OWL.ObjectProperty) not in g:
            if not list(g.objects(s, RDFS.comment)):
                 issues.append(f"[P08] Missing comment for Individual/Property: {str(s).split('/')[-1].split('#')[-1]}")

    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        if not list(g.objects(p, RDFS.domain)):
            issues.append(f"[P11] Missing Domain for Property: {str(p).split('/')[-1].split('#')[-1]}")
        if not list(g.objects(p, RDFS.range)):
            issues.append(f"[P11] Missing Range for Property: {str(p).split('/')[-1].split('#')[-1]}")

    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        if not list(g.objects(p, OWL.inverseOf)):
            issues.append(f"[P13-Warning] No inverse relation for: {str(p).split('/')[-1].split('#')[-1]}")

    return issues

if __name__ == "__main__":
    file_to_check = "UCO_FINAL.xml"
    if not os.path.exists(file_to_check):
        file_to_check = "UCO_FINAL.ttl"
        
    if os.path.exists(file_to_check):
        results = run_structural_check(file_to_check)
        for issue in results:
            pass