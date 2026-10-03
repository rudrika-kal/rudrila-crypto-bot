from __future__ import annotations

def windows(rows, train_size:int, test_size:int, step:int|None=None):
    step=step or test_size
    i=0
    while i+train_size+test_size<=len(rows):
        yield rows[i:i+train_size], rows[i+train_size:i+train_size+test_size]
        i+=step

def walk_forward(rows,train_size,test_size,tune_fn,test_fn,step=None):
    reports=[]
    for idx,(train,test) in enumerate(windows(rows,train_size,test_size,step)):
        params=tune_fn(train)
        metrics=test_fn(test,params)
        reports.append({'window':idx,'params':params,'metrics':metrics})
    return reports
