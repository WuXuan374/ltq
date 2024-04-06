from random import Random
from Selector import Hypothesis, NamesGenerator, TriplePatternSelector, Variable, FilterOpSelector, Selector
from SparqlGraph import SparqlGraph
import itertools

class ContingencyMatrix:
    def __init__(self):
        self.tp = 0
        self.tn = 0
        self.fp = 0
        self.fn = 0

    def __str__(self):
        return 'tp={} fp={} fn={} tn={}'.format(self.tp, self.fp, self.fn, self.tn)

class Engine:
    def __init__(self, graph, positive, negative):
        self.graph:SparqlGraph = graph
        self.positive = set(positive)
        self.negative = set(negative)
        self.hypothesis = Hypothesis()
        self.hypothesis_cm = ContingencyMatrix()
        self.ex_positive = None
        self.ex_negative = None
        self.random = Random(0xbeef)

    def _sparql_list(self, l, sep=" "):
        return sep.join([item.n3() for item in l]) # n3() 是 URIRef 的方法，检查 URI 是否合法
    
    def _sparql_positive(self, sep=" "):
        return self._sparql_list(self.positive, sep)
  
    def _sparql_negative(self, sep=" "):
        return self._sparql_list(self.negative, sep)
    
    def _args(self, root):
        s_gen = NamesGenerator("?s", "?s_anon") # 生成变量名
        t_gen = NamesGenerator("?t", "?t_anon")
        n = 30
        if len(self.positive) <= n:
            pos = self.positive
        else:
            pos = self.random.sample(self.positive, n)
        if len(self.negative) <= n:
            neg = self.negative
        else:
            neg = self.random.sample(self.negative, n)
        args = {
            'positive': self._sparql_list(pos),
            'negative': self._sparql_list(neg),
            's_selector': self.hypothesis.sparql(s_gen),
            't_selector': self.hypothesis.sparql(t_gen),
            'n_pos': len(pos),
            'n_neg': len(neg),
            's_root': s_gen[root],
            't_root': t_gen[root],
            'tp': '?tp',
            'fp': '?fp',
        }
        args['measure'] = "({tp}/({tp}+{fp}) as ?precision) ({tp}/{n_pos} as ?recall) (2*({tp}/({tp}+{fp}))*({tp}/{n_pos}) / ({tp}/({tp}+{fp}) + {tp}/{n_pos}) as ?measure)".format_map(
            args)
        args['having'] = "(count(distinct ?s))/{n_pos} >= .99".format_map(args) # 这个条件就要求了 ?tp != 0, 因为 n_pos 一定是 >= 1 的
        return args
    
    def p(self, root):
        '''改成子查询的写法，避免部分 ?tp = 0 导致的整个查询出现 Division By Zero 错误'''
        query = '''
                select distinct ?p ?tp ?fp {measure} 
                where 
                {{
                    {{
                        select distinct ?p (count(distinct ?s) as ?tp) (count(distinct ?t) as ?fp)
                        where
                        {{
                            {{
                                {s_selector}
                                {s_root} ?p [] .
                                values ?s {{ {positive} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                            union
                            {{
                                {t_selector}
                                {t_root} ?p [] .
                                values ?t {{ {negative} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                        }}
                        group by ?p
                        having ({having})
                    }}
                }}
        '''.format_map(self._args(root))
        for row in self.graph.select(query):
            s = TriplePatternSelector(root, row['p'], Variable())
            if s not in self.hypothesis:
                yield s, row
    
    def po(self, root):
        query = '''
                select distinct ?p ?o ?tp ?fp {measure} 
                where
                {{
                    {{
                        select distinct ?p ?o (count(distinct ?s) as ?tp) (count(distinct ?t) as ?fp)
                        where 
                        {{
                            {{
                                {s_selector}
                                {s_root} ?p ?o .
                                values ?s {{ {positive} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                            union
                            {{
                                {t_selector}
                                {t_root} ?p ?o .
                                values ?t {{ {negative} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                        }}
                        group by ?p ?o
                        having ({having})
                    }}
                }}
                order by desc(?measure)
        '''.format_map(self._args(root))
        for row in self.graph.select(query):
            s = TriplePatternSelector(root, row['p'], row['o'])
            if s not in self.hypothesis:
                yield s, row
    
    def sp(self, root):
        query = '''
                select distinct ?p ?o ?tp ?fp {measure} 
                where
                {{
                    {{
                        select distinct ?p ?o (count(distinct ?s) as ?tp) (count(distinct ?t) as ?fp)
                        where
                        {{
                            {{
                                {s_selector}
                                ?o ?p {s_root} .
                                values ?s {{ {positive} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                            union
                            {{
                                {t_selector}
                                ?o ?p {t_root} .
                                values ?t {{ {negative} }}
                                FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                            }}
                        }}
                        group by ?p ?o
                        having ({having})
                    }}
                }}
                order by desc(?measure)
        '''.format_map(self._args(root))
        for row in self.graph.select(query):
            s = TriplePatternSelector(row['o'], row['p'], root)
            if s not in self.hypothesis:
                yield s, row
    
    def comp(self, root):
        args = self._args(root)
        for op in '<=', '>=':
            args['op'] = op
            query = '''
                    select distinct ?p ?l ?tp ?fp {measure} 
                    where
                    {{
                        {{
                            select distinct ?p ?l (count(distinct ?s) as ?tp) (count(distinct ?t) as ?fp)
                            where
                            {{
                                {{
                                    {s_selector}
                                    {s_root} ?p ?xl.
                                    values ?s {{ {positive} }}
                                    filter(isLiteral(?xl))
                                    FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                                }}
                                union
                                {{
                                    {t_selector}
                                    {t_root} ?p ?xl.
                                    values ?t {{ {negative} }}
                                    filter(isLiteral(?xl))
                                    FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                                }}
                                filter(?xl {op} ?l)
                                {{
                                    select distinct ?p ?l
                                    where
                                    {{
                                        {s_selector}
                                        {s_root} ?p ?l.
                                        values ?s {{ {positive} }}
                                        filter(isLiteral(?l))
                                        FILTER (strstarts(str(?p),"http://rdf.freebase.com/ns/")) .
                                    }}
                                }}
                            }}
                            group by ?p ?l
                            having ({having})
                        }}
                    }}
            '''.format_map(args)
            for row in self.graph.select(query):
                s = FilterOpSelector(root, row['p'], op, row['l'])
                if s not in self.hypothesis:
                    yield s, row
    
    def _new_positive_examples(self):
        return []
    
    def _new_negative_examples(self):
        selector = self.hypothesis[:-1].sparql(NamesGenerator('?uri', '?plus'))
        if len(selector.strip()) == 0:
            selector = '?uri ?p ?o' # 测试过了，这里不能加 filter, 加了就超时，离谱
        args = {
            'known': self._sparql_list(itertools.chain(self.positive, self.negative), sep=", "),
            'selector': selector,
            'minus': self.hypothesis.sparql(NamesGenerator('?uri', '?minus')),
        }
        query = '''select distinct ?uri ?comment
                where {{
                    {{
                        {{
                            {selector}
                        }}
                        minus
                        {{
                            {minus}
                        }}
                    }}
                    filter(?uri not in ({known}))
                    optional {{?uri rdfs:comment ?comment}}
                }}
                limit 3
        '''.format_map(args)
        return [row for row in self.graph.select(query)]

    def new_examples(self):
        return self._new_positive_examples(), self._new_negative_examples()
    
    def final_query(self):
        args = {
            'selector': self.hypothesis.sparql(NamesGenerator('?uri', '?anon'))
        }
        query = "select distinct ?uri\nwhere\n{{\n{selector}}}".format_map(args)
        return query

    def _hypothesis_quality(self):
        
        # ?tp = 0 会导致计算 f1 时出现 Division By Zero
        query = '''
            select distinct ?tp ?fp {measure} 
            where
            {{
                filter (?tp > 0) 
                {{
                    select distinct (count(distinct ?s) as ?tp) (count(distinct ?t) as ?fp)
                    where
                    {{
                        {{
                            {s_selector}
                            values ?s {{ {positive} }}
                        }}
                        union
                        {{
                            {t_selector}
                            values ?t {{ {negative} }}
                        }}
                    }}
                }}
            }}
            
        '''.format_map(self._args(Selector.placeholder))
        try: # 有可能结果为空，故补充 try-catch
            result = [row for row in self.graph.select(query)]
            assert len(result) == 1, "Empty execution result"
            if 'measure' not in result[0]:  # znaczy obliczenia sie nie powiodly
                return 0
            else:
                return result[0]['measure'].value
        except Exception as e:
            print(f"query: {query}; exception: {e}")
            return 0

    def hypothesis_good_enough(self):
        m = self._hypothesis_quality()
        print("hypotesis quality", m)
        return m > .99

    def label_examples(self, lab_positive, lab_negative):
        self.hypothesis_cm = ContingencyMatrix()
        assert len(lab_positive) == len(self.ex_positive)
        assert len(lab_negative) == len(self.ex_negative)
        n = len(lab_positive) + len(lab_negative)
        for ex, label in zip(self.ex_positive, lab_positive):
            if label:
                self.positive.add(ex['uri'])
                self.hypothesis_cm.tp += 1.0 / n
            else:
                self.negative.add(ex['uri'])
                self.hypothesis_cm.fp += 1.0 / n
        for ex, label in zip(self.ex_negative, lab_negative):
            if label:
                self.positive.add(ex['uri'])
                self.hypothesis_cm.fn += 1.0 / n
            else:
                self.negative.add(ex['uri'])
                self.hypothesis_cm.tn += 1.0 / n
        print(self.hypothesis_cm)
    
    def _variables(self, source=None):
        if source is None:
            source = self.hypothesis
        result = []
        for x in source:
            result += x.variables
        if len(result) == 0:
            result.append(Selector.placeholder)
        return set(result)

    def step(self):
        if self.hypothesis_cm.fn > 0:
            if len(self.hypothesis) > 0:
                self.hypothesis = self.hypothesis[:-1]
            else:
                raise Exception("I can not make an empty hypothesis even more general!")
        restarted = False
        while True:
            while len(self.hypothesis) > 0:
                p, n = self.new_examples()
                if len(p) > 0 and len(n) > 0:
                    break # 能够生成新的 example --> 我们的场景下主要是负例，则会对当前 hypothesis 进行 refine
                else:
                    self.hypothesis.pop()
            print(self.hypothesis.sparql())
            print("Variables", self._variables())
            candidates = []
            for var in self._variables():
                candidates += self.po(var)
                candidates += self.sp(var)
                candidates += self.comp(var)
                candidates += self.p(var)
            candidates = sorted(candidates, key=lambda x: (x[1]['measure'].value, x[1]['precision'].value), reverse=True)
            candidates = [cand[0] for cand in candidates]
            for cand in candidates:
                self.hypothesis.append(cand)
                print("#positive = {} #negative = {}".format(len(self.positive), len(self.negative)))
                print("Refined hypothesis is:")
                print(self.hypothesis.sparql())
                self.ex_positive, self.ex_negative = self.new_examples()
                if self.hypothesis_good_enough():
                    return
                if len(self.ex_positive) > 0 and len(self.ex_negative) > 0:
                    return # 还会被进一步 refine
                self.hypothesis.pop()
            if self.hypothesis.pop() is None:
                if restarted:
                    # raise Exception("Uh-huh, and what now?")
                    return # 抛出异常的话，就不会记录之前存下来的查询了
                else:
                    restarted = True