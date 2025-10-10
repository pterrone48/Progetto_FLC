import os
import sys
import traceback
from datetime import datetime
import pandas as pd
from owlready2 import get_ontology, Thing

HAVE_EMBEDDINGS = False
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    HAVE_EMBEDDINGS = True
except Exception:
    HAVE_EMBEDDINGS = False

# Fuzzy 
try:
    from fuzzywuzzy import fuzz
except Exception:
    fuzz = None

OWL_PATH = r"C:\Users\Utente\Downloads\uco_1_5.owl"
EXCEL_PATH = r"C:\Users\Utente\Desktop\Cyber Events Database - 2014-2024 + Jan & Aug 2025.xlsx"
OUTPUT_OWL = r"C:\Users\Utente\Desktop\ontologia_popolata_semantic.owl"
REPORT_CSV = r"C:\Users\Utente\Desktop\ontologia_popolata_semantic_mapping_report.csv"
CLASSES_DEBUG_CSV = r"C:\Users\Utente\Desktop\onto_classes_debug.csv"

NUM_ROWS_TO_TEST = None   

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.56
FUZZY_THRESHOLD = 72
MAX_SUGGESTIONS = 5

# Mapping
PROPERTY_MAPPING = {
    "event_date": "hasEventDate",
    "year": "hasYear",
    "month": "hasMonth",
    "actor": "hasActor",
    "actor_type": "hasActorType",
    "organization": "hasOrganization",
    "industry": "hasIndustry",
    "motive": "hasMotive",
    "event_type": "hasEventType",
    "event_subtype": "hasEventSubtype",
    "description": "hasDescription",
    "country": "hasCountry",
    "actor_countr": "hasActorCountry",
    "state": "hasState",
    "county": "hasCounty",
    "slug": None,

}

def safe_getattr_onto(onto, name):
    return getattr(onto, name, None)

def list_classes_info(onto):
    out = []
    for c in onto.classes():
        labels = [str(l) for l in getattr(c, "label", [])] if getattr(c, "label", None) else []
        sup_names = [s.name for s in c.is_a if hasattr(s, "name")]
        out.append({
            "name": c.name,
            "iri": c.iri,
            "labels": " | ".join(labels),
            "superclasses": " | ".join(sup_names)
        })
    return out

def build_class_reprs(onto):
    """Return list of tuples (class_obj, [repr strings])"""
    out = []
    for c in onto.classes():
        reprs = []
        if getattr(c, "label", None):
            reprs.extend([str(l) for l in c.label])
        reprs.append(c.name)
        out.append((c, list(dict.fromkeys([r for r in reprs if r]))))
    return out

def compute_embeddings_for_corpus(model, class_reprs):
    texts = [" | ".join(reprs) for _, reprs in class_reprs]
    embs = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embs

def semantic_match(desc, class_reprs, class_embeddings, model):
    desc_emb = model.encode([desc], show_progress_bar=False, convert_to_numpy=True)
    sims = cosine_similarity(desc_emb, class_embeddings)[0]
    results = []
    for i, score in enumerate(sims):
        c_obj, reprs = class_reprs[i]
        results.append((c_obj, float(score), " | ".join(reprs)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results

def fuzzy_match(desc, class_reprs, topn=5):
    results = []
    for c_obj, reprs in class_reprs:
        best = 0
        for r in reprs:
            try:
                s = fuzz.partial_ratio(desc.lower(), r.lower()) if fuzz else 0
            except Exception:
                s = 0
            if s > best:
                best = s
        results.append((c_obj, best, " | ".join(reprs)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:topn]

def find_prop_by_similar_name(onto, col_name):
    """Cerca proprietà nell'ontologia con nomi simili alla colonna."""
    col_normal = col_name.lower().replace(" ", "").replace("_", "")
    candidates = []
    for p in list(onto.properties()):
        pname = getattr(p, "name", None)
        if not pname:
            continue
        pn = pname.lower().replace(" ", "").replace("_", "")
        if col_normal in pn or pn in col_normal:
            candidates.append(pname)
    return candidates


def main():
    print(f"[{datetime.now()}] Avvio script")

    if not os.path.exists(OWL_PATH):
        print("ERRORE: OWL non trovato:", OWL_PATH); return
    if not os.path.exists(EXCEL_PATH):
        print("ERRORE: Excel non trovato:", EXCEL_PATH); return

    onto = get_ontology(OWL_PATH).load()
    print(f"Ontologia caricata: {len(list(onto.classes()))} classi trovate.\n")

    # Debug
    classes_info = list_classes_info(onto)
    pd.DataFrame(classes_info).to_csv(CLASSES_DEBUG_CSV, index=False)
    print(f"Lista classi salvata in: {CLASSES_DEBUG_CSV}")

    class_reprs = build_class_reprs(onto)
    all_class_names_lower = [c.name.lower() for c, _ in class_reprs]

    model = None
    class_embeddings = None
    if HAVE_EMBEDDINGS:
        try:
            print("Carico modello embeddings:", EMBEDDING_MODEL)
            model = SentenceTransformer(EMBEDDING_MODEL)
            class_embeddings = compute_embeddings_for_corpus(model, class_reprs)
            print("Embeddings create per classi.")
        except Exception as e:
            print("ATTENZIONE: problema caricamento embeddings:", e)
            model = None
            class_embeddings = None

    # read excel
    try:
        df = pd.read_excel(EXCEL_PATH)
    except Exception as e:
        print("ERRORE lettura Excel:", e)
        return

    if NUM_ROWS_TO_TEST:
        df = df.head(NUM_ROWS_TO_TEST)
    print(f"Caricate {len(df)} righe dal file Excel.\n")

    report = []

    with onto:
        for idx, row in df.iterrows():
            try:
                slug = row.get("slug", f"event_{idx}")
                instance_name = str(slug).replace(" ", "_")
                desc = str(row.get("description", "")).strip()
                desc_lower = desc.lower()

                matched_method = None
                matched_class = None
                matched_score = 0.0
                matched_repr = ""

                
                if model and class_embeddings is not None and desc:
                    sem_results = semantic_match(desc, class_reprs, class_embeddings, model)
                    top_cls, top_score, top_repr = sem_results[0]
                    if top_score >= SIMILARITY_THRESHOLD:
                        matched_method = "semantic"
                        matched_class = top_cls
                        matched_score = top_score
                        matched_repr = top_repr
                    else:
                        top_suggestions_sem = sem_results[:MAX_SUGGESTIONS]
                else:
                    top_suggestions_sem = []

                
                if matched_class is None and desc and fuzz:
                    fuzzy_results = fuzzy_match(desc, class_reprs, topn=MAX_SUGGESTIONS)
                    topf_cls, topf_score, topf_repr = fuzzy_results[0]
                    if topf_score >= FUZZY_THRESHOLD:
                        matched_method = "fuzzy"
                        matched_class = topf_cls
                        matched_score = topf_score / 100.0
                        matched_repr = topf_repr
                    else:
                        top_suggestions_fuzzy = fuzzy_results
                else:
                    top_suggestions_fuzzy = []

                
                if matched_class is None and desc:
                    for token in set(desc_lower.split()):
                        for c_obj, reprs in class_reprs:
                            for r in reprs:
                                if token in r.lower().split():
                                    matched_method = "lexical_token"
                                    matched_class = c_obj
                                    matched_score = 0.0
                                    matched_repr = r
                                    break
                            if matched_class:
                                break
                        if matched_class:
                            break

                
                if matched_class is None:
                    matched_method = "fallback_Thing"
                    matched_class = Thing
                    matched_score = 0.0
                    matched_repr = "Thing"

                
                try:
                    inst = matched_class(instance_name)
                except Exception as e:
                    print(f"ERRORE creazione istanza {instance_name} di {matched_class}: {e}")
                    traceback.print_exc()
                    continue

                
                for col in df.columns:
                    col_norm = str(col).strip()
                    if col_norm.lower() == "slug":
                        continue
                    prop_name = None
                    if col_norm.lower() in PROPERTY_MAPPING and PROPERTY_MAPPING[col_norm.lower()]:
                        prop_name = PROPERTY_MAPPING[col_norm.lower()]
                        if not hasattr(inst, prop_name):
                            sims = find_prop_by_similar_name(onto, prop_name)
                            if sims:
                                prop_name = sims[0]
                    else:
                        sims = find_prop_by_similar_name(onto, col_norm)
                        prop_name = sims[0] if sims else None

                    if not prop_name:
                        continue

                    try:
                        val = row.get(col)

                        if pd.isna(val) or val is None:
                          setattr(inst, prop_name, [])
                        else:
                           
                           if prop_name in ["hasYear", "hasMonth"]:
                             try:
                                v_to_set = int(val)
                             except:
                                v_to_set = None
                           elif prop_name == "hasEventDate":
                               
                               if isinstance(val, pd.Timestamp):
                                  v_to_set = val.to_pydatetime()
                               elif isinstance(val, datetime):
                                  v_to_set = val
                               else:
                                  v_to_set = pd.to_datetime(val).to_pydatetime()
                           elif prop_name == "hasAuthentication":
                              v_to_set = bool(val)
                           elif prop_name in ["hasSourceURL", "hasEmail"]:
                              v_to_set = str(val)  
                           else:
                              v_to_set = str(val)  

                           
                           if v_to_set is None:
                              setattr(inst, prop_name, [])
                           else:
                              setattr(inst, prop_name, [v_to_set])

                    except Exception as e:
                        print(f"ATTENZIONE: non posso assegnare '{prop_name}' a {instance_name}: {e}")

                report.append({
                    "row_index": idx,
                    "instance_name": instance_name,
                    "description_snippet": desc[:200],
                    "matched_method": matched_method,
                    "matched_class": getattr(matched_class, "name", str(matched_class)),
                    "matched_score": matched_score,
                    "matched_repr": matched_repr,
                })

                print(f"[{idx}] {instance_name} -> {getattr(matched_class,'name',str(matched_class))} ({matched_method}, score={matched_score})")

            except Exception as e:
                print(f"ERRORE riga {idx}: {e}")
                traceback.print_exc()
                continue

       try:
        onto.save(file=OUTPUT_OWL, format="rdfxml")
        print(f"\nOntologia salvata in: {OUTPUT_OWL}")
    except Exception as e:
        print("ERRORE salvataggio ontologia:", e)

    # report CSV
    try:
        pd.DataFrame(report).to_csv(REPORT_CSV, index=False)
        print(f"Report mapping salvato in: {REPORT_CSV}")
    except Exception as e:
        print("ERRORE salvataggio report:", e)

    print("Fine script.")

if __name__ == "__main__":
    main()
