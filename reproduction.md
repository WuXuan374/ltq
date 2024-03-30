# DBPedia 版本修改记录
## benchmark.py
将 DBPedia 替换成官方端口
## SparqlGraph.py
补充了单个 SPARQL 的超时时间
补充了一些 try-catch

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
## benchmarkFreebase.py
数据处理: 按照 LTQ 的逻辑，应该只处理了答案为 uri 的情况

PRF1 的计算，防止溢出
- f1 的计算改为 2 * P * R / (P+R), 不然容易出现 Division By Zero
- 另外在各种除法里面，补充 1e-10, 避免除数为 0

target 直接使用数据集中的 "answer" 项，不需要重新获取
positive 设置为 target, 即一开始就把所有答案给出
补充每个样本的查询超时时间限制

每个样本的答案: 只考虑 "entity" 类型的，代码中只能处理 URIRef, 写 SPARQL 查询的时候，多处都假定了答案是 URI
- 例如，label_examples() 能看出 LTQ 确实只能处理 URI

## EngingFreebase.py
Selector.py: 我认为这个文件中的代码和知识库无关，无需修改

- _new_positive_examples 直接返回空 list()
    - 因为前文已经一次性给出所有 positive examples 
    - 我认为这个做法是合理的；否则按照 LTQ 的做法， 查询得到新的 positive examples 之后，同样是通过 SPARQL 查询去查找可能的 query
- 调用 new_examples() 的地方, 逻辑保持不变
- _hypothesis_quality()
- 每个查询中，补充谓词的前缀约束
    - FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
- 写法上的修改，主要是把 PRF1 的计算放在外层，不然引擎会报错 + 有时候 Division By Zero

有一些抛出异常的地方，改成 print

测试: EngineTestsFreebase.py