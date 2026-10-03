from __future__ import annotations

def chronological_split(rows, train=.6, validation=.2):
    n=len(rows); a=int(n*train); b=int(n*(train+validation))
    return rows[:a],rows[a:b],rows[b:]

def no_overlap(*parts):
    ids=[]
    for p in parts: ids.extend(id(x) for x in p)
    return len(ids)==len(set(ids))
