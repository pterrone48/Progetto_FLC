import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from collections import Counter
from itertools import combinations

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('punkt_tab', quiet=True)

stop_words = set(stopwords.words('english'))  
lemmatizer = WordNetLemmatizer()

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    tokens = nltk.word_tokenize(text)
    tokens = [lemmatizer.lemmatize(w) for w in tokens if w not in stop_words]
    return tokens   

df = pd.read_excel("Cyber_Events_Database.xlsx")
df["tokens"] = df["description"].apply(clean_text)

all_tokens = [w for tokens in df["tokens"] for w in tokens]
word_counts = Counter(all_tokens)

top_n = 1000
top_words = [w for w, _ in word_counts.most_common(top_n)]
top_words_set = set(top_words)

cooc = Counter()

for tokens in df["tokens"]:
    unique_tokens = set(tokens) & top_words_set  
    for w1, w2 in combinations(unique_tokens, 2):
        cooc[(w1, w2)] += 1
        cooc[(w2, w1)] += 1  

cooc_matrix = pd.DataFrame(0, index=top_words, columns=top_words)

for (w1, w2), count in cooc.items():
    cooc_matrix.at[w1, w2] = count

cooc_matrix.to_excel("matrice_cooccorrenze.xlsx")

# Il codice elabora il file Excel iniziale. Si utilizza Pandas per gestire i dati.
# La libreria NLTK pulisce il testo descrittivo e si applica la lemmatizzazione per normalizzare termini.
# Si isolano le mille parole più frequenti, questa scelta garantisce efficienza computazionale elevata. 
# Itertools individua le relazioni tra i token. 
# Si produce una matrice di cooccorrenze finale. L'output viene esportato in formato Excel.