import rdflib
import networkx as nx
INPUT_FILE = "C:\\Users\\Utente\\Desktop\\kb_completa.ttl"
OUTPUT_FILE = "C:\\Users\\Utente\\Desktop\\kb_completa.gexf"
print(f"Caricamento ontologia da {INPUT_FILE}")
g = rdflib.Graph()
g.parse(INPUT_FILE, format="turtle")
print(f"Ontologia caricata con {len(g)} triple RDF.")
G = nx.DiGraph()
print("Conversione delle triple RDF in nodi e archi")
for s, p, o in g:
    G.add_node(s)
    G.add_node(o)
    G.add_edge(s, o, label=p)
print(f"Grafo creato con {G.number_of_nodes()} nodi e {G.number_of_edges()} archi.")
nx.write_gexf(G, OUTPUT_FILE)
print(f"Conversione completata! File pronto per Gephi: {OUTPUT_FILE}")
