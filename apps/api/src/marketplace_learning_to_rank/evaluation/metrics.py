from __future__ import annotations
import math
import random

def dcg(labels,k): return sum((2**int(x)-1)/math.log2(i+2) for i,x in enumerate(labels[:max(0,k)]))
def ndcg(labels,k):
    ideal=dcg(sorted(labels,reverse=True),k)
    return dcg(labels,k)/ideal if ideal else 0.0
def recall_at_k(ranked_ids,relevant_ids,k):
    relevant=set(relevant_ids)
    return len(set(ranked_ids[:max(0,k)])&relevant)/len(relevant) if relevant else 0.0
def precision_at_k(labels,k,threshold=3):
    if k<=0:return 0.0
    top=labels[:k]
    return sum(label>=threshold for label in top)/k
def mrr_at_k(labels,k,threshold=3):
    return next((1/(i+1) for i,x in enumerate(labels[:max(0,k)]) if x>=threshold),0.0)
def bootstrap_mean(values:list[float],seed:int=42,samples:int=1000,confidence:float=.95):
    if not values:return {"mean":0.0,"lower":0.0,"upper":0.0,"n":0}
    rng=random.Random(seed); n=len(values); means=[]
    for _ in range(max(1,samples)):
        means.append(sum(values[rng.randrange(n)] for _ in range(n))/n)
    means.sort(); alpha=(1-confidence)/2
    return {"mean":sum(values)/n,"lower":means[int(alpha*(len(means)-1))],"upper":means[int((1-alpha)*(len(means)-1))],"n":n}
def paired_bootstrap_difference(left:list[float],right:list[float],seed:int=42,samples:int=1000):
    if len(left)!=len(right):raise ValueError("Paired metric vectors must align")
    diffs=[b-a for a,b in zip(left,right)]
    interval=bootstrap_mean(diffs,seed,samples)
    interval["interpretation"]="interval includes zero" if interval['lower']<=0<=interval['upper'] else "interval excludes zero; synthetic offline evidence only"
    return interval
