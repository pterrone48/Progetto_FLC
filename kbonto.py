import os
import re
import torch
import rdflib
import pandas as pd
from tqdm import tqdm
from owlready2 import *
from datetime import datetime
from sentence_transformers import SentenceTransformer, util

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
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    g_init = rdflib.Graph()
    g_init.parse(os.path.join(current_dir, UCO_FILE_TTL), format="turtle")
    temp_xml_bridge = os.path.join(current_dir, "temp_uco_bridge.owl")
    g_init.serialize(destination=temp_xml_bridge, format="xml")
    
    model = SentenceTransformer('all-mpnet-base-v2')
    onto = get_ontology(os.path.abspath(temp_xml_bridge)).load()
    df = pd.read_excel(os.path.join(current_dir, EXCEL_FILE)).head(500)
    
    with onto:
        for p in list(onto.properties()):
            try:
                if not p.domain: p.domain = [Thing]
            except: pass
            try:
                if not p.range: p.range = [str if isinstance(p, DataPropertyClass) else Thing]
            except: pass
            
            if isinstance(p, ObjectPropertyClass) and not p.inverse_property:
                inv_name = f"is_{p.name}_of" if not p.name.startswith("has") else p.name.replace("has", "is") + "_of"
                try:
                    new_inv = types.new_class(inv_name, (ObjectProperty,))
                    new_inv.inverse_property = p
                    if hasattr(p.range, "storid") or (isinstance(p.range, list) and len(p.range) > 0):
                        new_inv.domain = p.range
                    if hasattr(p.domain, "storid") or (isinstance(p.domain, list) and len(p.domain) > 0):
                        new_inv.range = p.domain
                except: pass

        for cls in onto.classes():
            if not cls.comment:
                cls.comment.append(f"Formal definition for {cls.name} within the cybersecurity domain.")

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
                if val_str.lower() in ["undetermined", "unknown", "n/a", "nan"]: continue

                is_year = bool(re.fullmatch(r'\d{4}', val_str))
                col_emb = model.encode(str(col), convert_to_tensor=True)

                o_sims = util.cos_sim(col_emb, o_embs)[0]
                if o_sims.max() > 0.30:
                    op = obj_p[o_sims.argmax()]
                    if "hascve_id" in op.name.lower(): continue
                    try:
                        t_cls = Thing
                        if "victim" in col.lower(): t_cls = next((c for c in all_c if "Victim" in c.name), Thing)
                        elif "actor" in col.lower() or "launched" in col.lower(): t_cls = next((c for c in all_c if "ThreatActor" in c.name), Thing)
                        
                        t_node = t_cls(clean_iri(val_str))
                        if not t_node.comment:
                            t_node.comment.append(f"Entity representing {val_str}")
                        
                        if not t_node in getattr(main_inst, op.python_name):
                            getattr(main_inst, op.python_name).append(t_node)
                    except: pass

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

    temp_nt = os.path.join(current_dir, "temp_final.nt")
    onto.save(file=temp_nt, format="ntriples")
    
    g_final = rdflib.Graph()
    g_final.parse(temp_nt, format="nt")
    
    xml_output = os.path.join(current_dir, "UCO_FINAL.xml")
    ttl_output = os.path.join(current_dir, "UCO_FINAL.ttl")
    
    g_final.serialize(destination=xml_output, format="xml")
    g_final.serialize(destination=ttl_output, format="turtle")
    
    if os.path.exists(temp_nt): os.remove(temp_nt)
    if os.path.exists(temp_xml_bridge): os.remove(temp_xml_bridge)

if __name__ == "__main__":
    run_validated_injection()