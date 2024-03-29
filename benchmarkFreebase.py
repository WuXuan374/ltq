import json
import random
import time
import itertools
from tqdm import tqdm
from rdflib import URIRef
import logging
from common import NS_PREFIX
from EngineFreebase import Engine
from SparqlGraph import SparqlGraph
from common import SPARQL_wrapper_path_official, SPARQL_wrapper_path_dkilab



def load_json(fname, mode="r", encoding="utf8"):
    if "b" in mode:
        encoding = None
    with open(fname, mode=mode, encoding=encoding) as f:
        return json.load(f)

def evaluate(graph:SparqlGraph, query, target):
    target = set(target)
    result = set([row['uri'] for row in graph.select(query)])
    missing = target - result
    unexpected = result - target
    tp = len(result & target)
    fp = len(unexpected)
    prec = tp / max([(tp + fp), 1e-10]) 
    recall = tp / max([len(target), 1e-10])
    return {'prec': prec, 'recall': recall, 'f1': 2*prec*recall / max([(prec + recall), 1e-10]), 'missing': list(missing),
            'unexpected': list(unexpected)}

def get_shortened_evaluation_result(e):
    return {
        'prec': e["prec"], 'recall': e["recall"], 'f1': e["f1"], 'missing': list(e["missing"])[:5],
        'unexpected': list(e["unexpected"])[:5]
    }

def benchmark(q, negative, sparql_graph, logger, detection_timeout):
    example_start_time = time.time()
    target = list(set(q["answer"]))
    if len(target) == 0:
        return None
    positive = set(target) # 一开始就把所有答案给出
    # sample_num = min(len(target), 5)
    # positive = random.sample(target, sample_num)
    negative = negative - set(target)
    assert len(negative) > 0
    eng = Engine(sparql_graph, positive, list(negative))
    log = []
    for i in range(0, 10):
        n_steps = 0
        n_pos = 0
        n_neg = 0
        iteration_start = time.time()
        if iteration_start - example_start_time > detection_timeout:
            return log
        while not eng.hypothesis_good_enough():
            eng.step()
            n_steps += 1
            labels = []
            n_pos += len(eng.ex_positive)
            n_neg += len(eng.ex_negative)
            for ex in itertools.chain(eng.ex_positive, eng.ex_negative):
                labels.append(ex['uri'] in target)
            eng.label_examples(labels[:len(eng.ex_positive)], labels[len(eng.ex_positive):])
            if time.time() - example_start_time > detection_timeout:
                break
        
        iteration_end = time.time()
        # evaluation 这边耗时不会太长，就不做检查了
        logger.info("Starting evaluation")
        e = evaluate(sparql_graph, eng.final_query(), target)
        log_line = {'eval': get_shortened_evaluation_result(e),
                    'runtime': {'steps': n_steps, 'requests_p': n_pos, 'requests_n': n_neg},
                    'query': eng.final_query(),
                    'perf': {'start': iteration_start, 'end': iteration_end}}
        logger.info(get_shortened_evaluation_result(e))
        missing = list(e['missing'])
        ue = list(e['unexpected'])
        if len(missing) > 0:
            if len(missing) > 5:
                missing = random.sample(missing, 5)
            eng.positive |= set(missing)
            log_line['added_positive'] = list(missing)
        if len(ue) > 0:
            if len(ue) > 5:
                ue = random.sample(ue, 5)
            eng.negative |= set(ue)
            log_line['added_negative'] = list(missing)
        log.append(log_line)
        if len(ue) == 0 and len(missing) == 0:
            break
    return log

def load_queries(src_path):
    """
    读取数据的同时，也生成 6 个 random negative samples
    """
    src_data = load_json(src_path)
    processed_data = list()
    answer_set = set()

    for item in tqdm(src_data):
        processed_item = {
            "answer": [
                URIRef(f"{NS_PREFIX}{ans['mid']}")
                for ans in item["answer"]
                if ans['type'] == 'entity'
            ],
            "golden_sparql_query": item["golden_sparql_query"]
        } # 我认为 LTQ 只能处理答案为 uri 的情况
        processed_data.append(processed_item) 
        answer_set.update(processed_item["answer"])

    negative_examples = set(random.sample(answer_set, 6))
    
    return processed_data, negative_examples

def setup_custom_logger(log_file_name):
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    fileHandler = logging.FileHandler(log_file_name, mode='a')
    fileHandler.setFormatter(formatter)

    # 根据日志文件名，创建 Logger 实例；可以从不同的地方写入相同的 Log 文件
    logger = logging.getLogger(log_file_name)
    logger.setLevel(logging.INFO)
    logger.addHandler(fileHandler)
    logger.addHandler(logging.StreamHandler()) # Write to stdout as well
    time_ = time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())
    logger.info(f"Start logging: {time_}")

    return logger

def main():
    random.seed(12345)
    args = dict()
    args["data_file"] = "data/webqsp_test_0_1000_linking.json"
    args["output_path"] = 'data/webqsp_test_0_1000_output.json'
    args["log_path"] = 'data/webqsp_test_0_1000_log.txt'
    args["sparql_timeout"] = 60
    args["detection_timeout"] = 240
    args["endpoint_url"] = SPARQL_wrapper_path_official
    logger = setup_custom_logger(args["log_path"])
    logger.info("arguments")
    for (key, value) in args.items():
        logger.info(f"{key}: {value}")
    queries, negative_examples = load_queries(args["data_file"])
    sparql_graph = SparqlGraph(args["endpoint_url"], args["sparql_timeout"], logger)
    for q in queries[:1]:
        logger.info(q['golden_sparql_query'])
        data = {'query': q}
        try:
            log = benchmark(q, negative_examples, sparql_graph, logger, args["detection_timeout"])
            data['log'] = log
        except Exception as e:
            data['exception'] = str(e)
        with open(args["output_path"], 'at') as f:
            print(json.dumps(data), file=f)
        logger.info("=============================================")

if __name__ == '__main__':
    main()