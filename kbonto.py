from owlready2 import *
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import re
from datetime import datetime
from tqdm import tqdm

UCO_FILE = "uco_1.5.owl"
EXCEL_FILE = "Cyber_Events_Database.xlsx"

def is_valid_val(prop_name, val):
    v = str(val).lower()
    if v in ["undetermined", "unknown", "nan", "n/a"]: return False
    if "cve" in prop_name.lower() and not re.search(r'cve-\d{4}-\d+', v): return False
    if "date" in prop_name.lower() and not re.search(r'\d{4}', v): return False
    if "month" in prop_name.lower() and re.fullmatch(r'\d{4}', str(val)): return False
    return True

def clean_iri(text):
    text = re.sub(r'[^a-zA-Z0-9_]', '_', str(text))
    return text[:40].strip('_')

def adapt_value(prop, val):
    if not prop.range: return str(val)
    target = prop.range[0]
    try:
        if target == datetime or "dateTime" in str(target):
            return pd.to_datetime(val).to_pydatetime()
        if target == int: return int(float(val))
        if target == float: return float(val)
        return str(val)
    except: return str(val)

def run_validated_injection():
    model = SentenceTransformer('all-mpnet-base-v2')
    onto = get_ontology(UCO_FILE).load()
    df = pd.read_excel(EXCEL_FILE).head(500)
    
    with onto:
        all_c = list(onto.classes())
        all_p = list(onto.properties())
        obj_p = [p for p in all_p if isinstance(p, ObjectPropertyClass)]
        dat_p = [p for p in all_p if isinstance(p, DataPropertyClass)]
        
        c_embs = model.encode([c.name for c in all_c], convert_to_tensor=True)
        o_embs = model.encode([p.name for p in obj_p], convert_to_tensor=True)
        d_embs = model.encode([p.name for p in dat_p], convert_to_tensor=True)

        prop_year = getattr(onto, "hasYear", None)

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Iniezione"):
            d_emb = model.encode(str(row.get('description', '')), convert_to_tensor=True)
            main_inst = all_c[util.cos_sim(d_emb, c_embs)[0].argmax()](clean_iri(row['slug']))

            for col, val in row.items():
                if col == 'slug' or pd.isna(val): continue
                col_emb = model.encode(str(col), convert_to_tensor=True)
                val_str = str(val)
                is_year = bool(re.fullmatch(r'\d{4}', val_str))

                if is_year and prop_year:
                    try:
                        f_val = adapt_value(prop_year, val)
                        if hasattr(main_inst, prop_year.python_name):
                            attr = getattr(main_inst, prop_year.python_name)
                            if isinstance(attr, list): attr.append(f_val)
                            else: setattr(main_inst, prop_year.python_name, f_val)
                        continue
                    except: pass

                o_sims = util.cos_sim(col_emb, o_embs)[0]
                if o_sims.max() > 0.25:
                    op = obj_p[o_sims.argmax()]
                    if op.name == "hasCampaign" and "country" in col.lower(): continue
                    if op.name == "hasIncident" and is_year: continue

                    if is_valid_val(op.name, val):
                        try:
                            t_cls = op.range[0] if op.range and isinstance(op.range[0], (type, ClassConstruct)) else Thing
                            t_node = t_cls(clean_iri(val))
                            getattr(main_inst, op.python_name).append(t_node)
                        except: pass

                d_sims = util.cos_sim(col_emb, d_embs)[0]
                if d_sims.max() > 0.25:
                    dp = dat_p[d_sims.argmax()]
                    if dp.name == "hasIncident" and is_year: continue
                    if dp.name == "hasYear": continue 

                    if is_valid_val(dp.name, val):
                        try:
                            f_val = adapt_value(dp, val)
                            attr = getattr(main_inst, dp.python_name)
                            if isinstance(attr, list): attr.append(f_val)
                            else: setattr(main_inst, dp.python_name, f_val)
                        except: pass

    onto.save("FINALONTO.owl")

if __name__ == "__main__":
    run_validated_injection()

# Si raccordano le analisi precedenti all'iniezione. Si utilizza il file Excel come input. 
# Si opera sull'ontologia UCO tramite Owlready2mentre si calcolano gli embedding delle proprietà ontologiche. 
# Si applica la similarità del coseno semantica, il modello all-mpnet-base-v2 garantisce alta precisione. 
# Si imposta una soglia minima di 0.25. Sotto questa soglia, i mapping vengono scartati.
# Si filtrano manualmente i falsi positivi semantici. Si forza l'anno tramite regex a 4 cifre.