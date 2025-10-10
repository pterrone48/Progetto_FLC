import pandas as pd

df = pd.read_excel("/Users/user/Desktop/classifica_concorrenze.xlsx")  

ttl_content = """
@prefix : <http://www.example.org/cyber#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Keyword rdf:type owl:Class .

:coOccursWith rdf:type owl:ObjectProperty ;
              rdfs:domain :Keyword ;
              rdfs:range :Keyword .

:occurrences rdf:type owl:DatatypeProperty ;
             rdfs:domain :Keyword ;
             rdfs:range xsd:integer .
"""

words = set(df["Parola1"]).union(set(df["Parola2"]))

for w in words:
    ttl_content += f":{w} rdf:type :Keyword .\n"

for _, row in df.iterrows():
    w1, w2, occ = row["Parola1"], row["Parola2"], int(row["Concorrenze"])
    ttl_content += f":{w1} :coOccursWith :{w2} .\n"
    ttl_content += f":{w1}_{w2}_rel :occurrences \"{occ}\"^^xsd:integer .\n"

with open("/Users/user/Desktop/cooccorrenze.owl.ttl", "w") as f:
    f.write(ttl_content)

print("File OWL creato su Desktop: cooccorrenze.owl.ttl")
