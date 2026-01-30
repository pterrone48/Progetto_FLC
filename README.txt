C.E.D.xlsx --> cooccorrenze.py --> matrice_cooccorrenze.xlsx --> cooccorrenzeclassifier.py --> classifica_cooccorrenze --> findcouples.py--
--> uco_1_5.ttl(ttl viene letto meglio di owl) + ontologyadd.xlsx --> addentities.py --> uco_1_5_enriched.ttl --> kbonto.py --> FINALONTO.ttl

REASONER : Pellet

QUERY SPARQL DI PROVA: Query_SPARQL_Prova.txt (Utilizzabile plugin integrato per SPARQL Query)

installare dopo requirements:

import nltk
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('punkt')

python -m spacy download en_core_web_sm