import gzip
from SparqlGraph import SparqlGraph
from rdflib import URIRef
from collections import defaultdict
from tqdm import tqdm

sparql_graph = SparqlGraph('https://dbpedia.org/sparql', timeout=60, logger=None)

def load_queries():
    with gzip.open('selected_queries.txt.gz', 'rt') as f:
        for n, line in enumerate(f):
            if n % 2 == 1:
                yield line.strip()

def answer_statistics():
    queries = load_queries()
    answer_freq_list = list()
    for q in tqdm(queries):
        target = []
        for row in sparql_graph.select(q):
            assert len(row.values()) == 1
            uri = list(row.values())[0]
            if isinstance(uri, URIRef):
                target.append(uri)
        answer_freq_list.append(len(target))
    print(f"answer_freq_list: {answer_freq_list}")
    print(f"Average: {sum(answer_freq_list) / len(answer_freq_list)}")

if __name__ == '__main__':
    answer_statistics()