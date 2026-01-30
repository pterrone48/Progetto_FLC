from owlready2 import *
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import re
from tqdm import tqdm
import torch
import os
import rdflib
from datetime import datetime

UCO_FILE_TTL = "uco_1_5_enriched.ttl" 
EXCEL_FILE = "Cyber_Events_Database.xlsx"

def clean_iri(text):
    text = re.sub(r'[^a-zA-Z0-9_]', '_', str(text))
    return text.strip('_')[:40] if text else "unknown_entity"

def adapt_value_by_range(val_str, prop):
    try:
        p_range = prop.range
        if int in p_range or any("integer" in str(r).lower() for r in p_range):
            only_digits = re.sub(r'\D', '', str(val_str))
            return int(only_digits[:4]) if only_digits else 0
        if datetime in p_range or any("datetime" in str(r).lower() for r in p_range):
            if re.fullmatch(r'\d{4}', str(val_str)):
                return datetime(int(val_str), 1, 1)
            return pd.to_datetime(val_str).to_pydatetime()
        return str(val_str)
    except:
        return str(val_str)

def run_validated_injection():
    print("Conversione Turtle in corso...")
    g_init = rdflib.Graph()
    g_init.parse(UCO_FILE_TTL, format="turtle")
    temp_xml = "temp_uco_bridge.owl"
    g_init.serialize(destination=temp_xml, format="xml")
    
    model = SentenceTransformer('all-mpnet-base-v2')
    onto = get_ontology(os.path.abspath(temp_xml)).load()
    df = pd.read_excel(EXCEL_FILE).head(500)
    
    with onto:
        pillars_kw = ["attack", "malware", "incident", "vulnerability", "exploit", "consequence"]
        all_c = list(onto.classes())
        pillar_bases = [c for c in all_c if any(k in c.name.lower() for k in pillars_kw)]
        pillar_set = set(pillar_bases)
        for pb in pillar_bases:
            pillar_set.update(pb.descendants())
        pillar_list = list(pillar_set)
        
        all_p = list(onto.properties())
        obj_p = [p for p in all_p if isinstance(p, ObjectPropertyClass)]
        dat_p = [p for p in all_p if isinstance(p, DataPropertyClass)]
        prop_year = next((p for p in dat_p if "hasyear" in p.name.lower()), None)
        
        p_embs = model.encode([c.name for c in pillar_list], convert_to_tensor=True)
        c_embs = model.encode([c.name for c in all_c], convert_to_tensor=True)
        o_embs = model.encode([p.name for p in obj_p], convert_to_tensor=True)
        d_embs = model.encode([p.name for p in dat_p], convert_to_tensor=True)

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Iniezione"):
            d_val = str(row.get('description', ''))
            d_emb = model.encode(d_val, convert_to_tensor=True)
            
            p_sims = util.cos_sim(d_emb, p_embs)[0]
            best_p_idx = p_sims.argmax().item()
            main_inst = pillar_list[best_p_idx](clean_iri(row['slug']))
            
            top_vals, top_idxs = torch.topk(util.cos_sim(d_emb, c_embs)[0], k=3)
            for val, idx in zip(top_vals, top_idxs):
                target_cls = all_c[idx.item()]
                if val > 0.60 and target_cls not in main_inst.is_a:
                    main_inst.is_a.append(target_cls)

            if d_val and d_val.lower() != 'nan':
                main_inst.comment.append(d_val)

            for col, val in row.items():
                if col in ['slug', 'description'] or pd.isna(val): continue
                val_str = str(val).strip()
                
                # FILTRO CRITICO: Se il valore è "undetermined" o simile, saltiamo l'iniezione per questa colonna
                if val_str.lower() in ["undetermined", "unknown", "n/a", "nan"]: continue

                is_year = bool(re.fullmatch(r'\d{4}', val_str))
                col_emb = model.encode(str(col), convert_to_tensor=True)

                # Object Properties
                o_sims = util.cos_sim(col_emb, o_embs)[0]
                if o_sims.max() > 0.30:
                    op = obj_p[o_sims.argmax()]
                    if "hascve_id" in op.name.lower(): continue
                    try:
                        t_cls = Thing
                        # Contestualizzazione automatica basata sul nome colonna
                        if "victim" in col.lower(): t_cls = next((c for c in all_c if "Victim" in c.name), Thing)
                        elif "actor" in col.lower() or "launched" in col.lower(): t_cls = next((c for c in all_c if "ThreatActor" in c.name), Thing)
                        
                        t_node = t_cls(clean_iri(val_str))
                        if not t_node in getattr(main_inst, op.python_name):
                            getattr(main_inst, op.python_name).append(t_node)
                    except: pass

                # Data Properties
                d_sims = util.cos_sim(col_emb, d_embs)[0]
                if d_sims.max() > 0.25:
                    dp = dat_p[d_sims.argmax()]
                    if is_year and prop_year: dp = prop_year

                    try:
                        if hasattr(main_inst, dp.python_name):
                            final_val = adapt_value_by_range(val_str, dp)
                            prop_attr = getattr(main_inst, dp.python_name)
                            if isinstance(prop_attr, list):
                                if final_val not in prop_attr: prop_attr.append(final_val)
                            else: setattr(main_inst, dp.python_name, final_val)
                    except: pass

    print("\nSalvataggio...")
    temp_nt = "temp_output.nt"
    onto.save(temp_nt, format="ntriples")
    final_g = rdflib.Graph()
    final_g.parse(temp_nt, format="nt")
    final_g.serialize(destination="UCO_POPULATED_FINAL.ttl", format="turtle")
    
    for f in [temp_xml, temp_nt]:
        if os.path.exists(f): os.remove(f)
    print("Fatto! File: UCO_POPULATED_FINAL.ttl")

if __name__ == "__main__":
    run_validated_injection()