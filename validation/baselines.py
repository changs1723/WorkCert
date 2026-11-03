"""Fixed-budget geometric baselines used only by the published benchmark.

RDP uses a best-first, fixed-budget adaptation of perpendicular-distance
Douglas--Peucker refinement. VW uses effective-area vertex removal. Both
normalize the two axes to unit range and preserve explicitly supplied anchors.
These are benchmark selectors, not third-party wrapper implementations.
"""
import heapq
import numpy as np


def normalized_coordinates(x, force):
    x=np.asarray(x,dtype=float); f=np.asarray(force,dtype=float)
    return (x-x[0])/(x[-1]-x[0]), (f-np.min(f))/(np.ptp(f) or 1.0)


def _anchors(n, anchors):
    ids={0,n-1}|set(int(i) for i in anchors)
    if any(i<0 or i>=n for i in ids):raise ValueError('Invalid anchor')
    return ids


def _perpendicular(x,y,a,b):
    if b-a<2:return 0.0,None
    dx=x[b]-x[a];dy=y[b]-y[a]
    distance=np.abs(dx*(y[a+1:b]-y[a])-dy*(x[a+1:b]-x[a]))/np.hypot(dx,dy)
    point=int(np.argmax(distance))
    return float(distance[point]),a+1+point


def rdp_indices(x,force,budget,anchors=()):
    """Best-first RDP refinement at an exact vertex budget, with anchors."""
    xn,yn=normalized_coordinates(x,force)
    chosen=_anchors(len(xn),anchors);budget=min(int(budget),len(xn))
    if budget<len(chosen):raise ValueError('Budget cannot retain required anchors')
    heap=[]
    def add(a,b):
        score,point=_perpendicular(xn,yn,a,b)
        if point is not None:heapq.heappush(heap,(-score,a,b,point))
    ids=sorted(chosen)
    for a,b in zip(ids[:-1],ids[1:]):add(a,b)
    while len(chosen)<budget:
        _,a,b,point=heapq.heappop(heap)
        chosen.add(point);add(a,point);add(point,b)
    return np.asarray(sorted(chosen),dtype=np.int64)


def rdp_epsilon_indices(x,force,epsilon):
    """Unanchored tolerance RDP; used for a third-party agreement check."""
    xn,yn=normalized_coordinates(x,force)
    chosen={0,len(xn)-1};stack=[(0,len(xn)-1)]
    while stack:
        a,b=stack.pop();score,point=_perpendicular(xn,yn,a,b)
        if point is not None and score>epsilon:
            chosen.add(point);stack.extend([(a,point),(point,b)])
    return np.asarray(sorted(chosen),dtype=np.int64)


def vw_hierarchy(x,force,anchors=()):
    """Return effective-area removal order, protecting endpoints and anchors."""
    xn,yn=normalized_coordinates(x,force);n=len(xn)
    protected=_anchors(n,anchors);prev=np.arange(n)-1;nxt=np.arange(n)+1
    alive=np.ones(n,dtype=bool);generation=np.zeros(n,dtype=np.int64)
    heap=[];order=[];last=0.0
    def add(i):
        if i in protected or not alive[i]:return
        a,b=int(prev[i]),int(nxt[i])
        area=.5*abs((xn[i]-xn[a])*(yn[b]-yn[a])-(xn[b]-xn[a])*(yn[i]-yn[a]))
        generation[i]+=1
        # Select by current triangle area; record a monotone effective area
        # separately. Clamping heap priorities changes subsequent tie order.
        heapq.heappush(heap,(float(area),i,int(generation[i])))
    for i in range(1,n-1):add(i)
    while heap:
        area,i,stamp=heapq.heappop(heap)
        if not alive[i] or stamp!=generation[i]:continue
        last=max(last,area);order.append((i,last));alive[i]=False
        a,b=int(prev[i]),int(nxt[i]);nxt[a]=b;prev[b]=a
        add(a);add(b)
    return order


def vw_indices(x,force,budget,anchors=()):
    chosen=_anchors(len(x),anchors);budget=min(int(budget),len(x))
    if budget<len(chosen):raise ValueError('Budget cannot retain required anchors')
    order=vw_hierarchy(x,force,anchors)
    removed={i for i,_ in order[:len(x)-budget]}
    return np.asarray([i for i in range(len(x)) if i not in removed],dtype=np.int64)


def vw_epsilon_indices(x,force,epsilon):
    removed={i for i,area in vw_hierarchy(x,force) if area<epsilon}
    return np.asarray([i for i in range(len(x)) if i not in removed],dtype=np.int64)
