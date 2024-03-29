# DBPedia 版本修改记录
## benchmark.py
将 DBPedia 替换成官方端口

# 代码理解过程
## benchmark.py
benchmark() 函数: 每个测试样例的处理过程
L35 - L44: 执行 golden query, 获取 positive examples
negative_example 对于所有样本都是固定的那6个（除非和 positive example 冲突）

## Engine.py
Engine 类包装了构造查询所需的函数，包括所需要的 SPARQL 查询
- 如果要改成 Freebase 或者 Wikidata 版本，感觉需要在这修改

一些需要修改的细节:
- 每个 step 会添加一些 positive example 和 negative example
    - 在我们的实验设置下，应该 positive examples 在一开始就给定？
终止条件:
- 执行结果一致的查询 / 10 good enough hypothesis

# Freebase 版本复现记录 
## benchmark_freebase.py
数据处理: 按照 LTQ 的逻辑，应该只处理了答案为 uri 的情况

evaluate():
- f1 的计算改为 2 * P * R / (P+R), 不然容易出现 Division By Zero
- 另外在各种除法里面，补充 1e-10, 避免除数为 0

补充每个样本的查询超时时间限制
## EngingFreebase.py
Selector.py: 我认为这个文件中的代码和知识库无关，无需修改
SparqlGraph.py: 类似我们的 execute_query() 方法，我认为同样无需修改
- follow SparqlGraph.py 里面的单元测试，应该确实无需修改

其中的 label_examples() 函数也能看出，LTQ 确实仅处理 URI

没有太多改动:
- _new_positive_examples 直接返回空 list()
    - 感觉这边可能有问题
- 调用 new_examples() 的地方, 逻辑保持不变
- _hypothesis_quality()
- 每个查询中，补充谓词的前缀约束
    - FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .

测试: EngineTestsFreebase.py