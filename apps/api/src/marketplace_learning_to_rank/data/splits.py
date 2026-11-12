from __future__ import annotations
import random
from collections import defaultdict
from marketplace_learning_to_rank.core.models import MarketplaceQuery

def intent_key(query:MarketplaceQuery)->tuple:
    return (query.category,tuple(sorted(x.casefold() for x in query.specialties)),tuple(sorted(x.casefold() for x in query.skills)))

def grouped_split(queries:list[MarketplaceQuery],seed:int)->dict[str,str]:
    groups=defaultdict(list)
    for query in queries:groups[intent_key(query)].append(query.query_id)
    if len(groups)<3:raise ValueError("At least three distinct category/specialty/skill intents are required for grouped train/validation/test splits")
    rng=random.Random(seed+17);keys=list(groups);rng.shuffle(keys);keys.sort(key=lambda key:len(groups[key]),reverse=True)
    n=len(queries);targets={"train":.70*n,"validation":.15*n,"test":.15*n};counts={key:0 for key in targets};group_counts={key:0 for key in targets};assignment={}
    for index,key in enumerate(keys):
        remaining=len(keys)-index;empty=[name for name in targets if group_counts[name]==0]
        if remaining<=len(empty):name=max(empty,key=lambda item:targets[item]-counts[item])
        else:name=max(targets,key=lambda item:targets[item]-counts[item])
        group_counts[name]+=1;counts[name]+=len(groups[key])
        for query_id in groups[key]:assignment[query_id]=name
    return assignment
