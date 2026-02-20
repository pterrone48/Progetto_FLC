import pandas as pd

ORIGIN = "matrice_cooccorrenze.xlsx"
OUTPUT = "classifica_cooccorrenze.xlsx"

def rebuild_cooccurrences(path, threshold=100):
    df = pd.read_excel(path, index_col=0)

    stack = df.stack().reset_index()
    stack.columns = ['Parola1', 'Parola2', 'Cooccorrenze']

    ranking = stack[stack['Cooccorrenze'] > threshold]

    ranking = ranking[ranking['Parola1'] < ranking['Parola2']]
    return ranking.sort_values(by='Cooccorrenze', ascending=False)

df_result = rebuild_cooccurrences(ORIGIN)
df_result.to_excel(OUTPUT, index=False)

# Il codice carica la matrice generata precedentemente. Si utilizza Pandas per ristrutturare i dati. 
# L'input è il file matrice_cooccorrenze.xlsx. Si applica la funzione stack per incolonnare.
# Si imposta un threshold di 100 occorrenze, questa scelta tecnica filtra il rumore statistico. 
# Si eliminano i duplicati speculari tra parole e si ottiene una classifica ordinata per rilevanza. 
# L'output viene salvato in classifica_cooccorrenze.xlsx, poi analizzano questi dati per selezionare entity. 
# I termini scelti arricchiranno l'ontologia UCO. Le nuove definizioni confluiscono in ontologyadd.xlsx.( a mano post lettura)