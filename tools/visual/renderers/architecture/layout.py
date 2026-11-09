"""Deterministic cluster placement and obstacle-aware orthogonal routing."""
from collections import defaultdict, deque
import heapq
import math
import unicodedata
from .validate import validate, ModelError


def wrap(text, units=26):
    lines=[];line='';size=0
    for char in text:
        width=0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in 'WF' or char in 'WMwm@%&' else 1.5 if char.isupper() else 1.25)
        if char=='\n' or (size+width>units and line):
            lines.append(line);line='';size=0
            if char=='\n':continue
        line+=char;size+=width
    if line:lines.append(line)
    return lines or ['']


def overlaps(a,b,pad=0):
    return a['x'] < b['x']+b['w']+pad and a['x']+a['w']+pad>b['x'] and a['y']<b['y']+b['h']+pad and a['y']+a['h']+pad>b['y']


def hits(a,b,r):
    # Rectangles are open: a route on the padded perimeter is safe.
    x,y=a;xx,yy=b
    if y==yy:return r['y']<y<r['y']+r['h'] and max(min(x,xx),r['x'])<min(max(x,xx),r['x']+r['w'])
    if x==xx:return r['x']<x<r['x']+r['w'] and max(min(y,yy),r['y'])<min(max(y,yy),r['y']+r['h'])
    raise ValueError('non-orthogonal segment')


def ranks(ids,edges):
    """SCC condensation makes feedback cycles legal without losing edges."""
    graph={x:[] for x in ids}
    for a,b in edges:
        if a in graph and b in graph and a!=b:graph[a].append(b)
    index={};low={};stack=[];active=set();components=[]
    def visit(v):
        index[v]=low[v]=len(index);stack.append(v);active.add(v)
        for n in sorted(set(graph[v])):
            if n not in index:visit(n);low[v]=min(low[v],low[n])
            elif n in active:low[v]=min(low[v],index[n])
        if low[v]==index[v]:
            c=[]
            while True:
                n=stack.pop();active.remove(n);c.append(n)
                if n==v:break
            components.append(sorted(c))
    for v in sorted(ids):
        if v not in index:visit(v)
    owner={v:i for i,c in enumerate(components) for v in c}
    arcs={(owner[a],owner[b]) for a,b in edges if a in owner and b in owner and owner[a]!=owner[b]}
    degree={i:sum(b==i for a,b in arcs) for i in range(len(components))}
    rank={i:0 for i in degree};q=deque(sorted(i for i,d in degree.items() if d==0))
    while q:
        a=q.popleft()
        for b in sorted(b for aa,b in arcs if aa==a):
            rank[b]=max(rank[b],rank[a]+1);degree[b]-=1
            if degree[b]==0:q.append(b)
    return {v:rank[owner[v]] for v in ids}


def placement_edges(model, owner):
    """Choose an acyclic ordering backbone; ALL original edges still get routed."""
    graph=defaultdict(set);selected=[]
    priority={'calls':0,'data_flow':1,'depends_on':2,'feedback':3}
    def reachable(start,target):
        seen=set();todo=[start]
        while todo:
            n=todo.pop()
            if n==target:return True
            if n not in seen:seen.add(n);todo.extend(graph[n])
        return False
    for e in sorted(model['relations'],key=lambda e:(priority[e['type']],e['id'])):
        a,b=owner[e['source']],owner[e['target']]
        if e['type']=='feedback' or a==b or reachable(b,a):continue
        graph[a].add(b);selected.append((a,b))
    return selected


def positions(ids, edges, mode, cw, ch):
    ids=sorted(ids)
    degree={x:sum(x in edge for edge in edges) for x in ids}
    if mode=='auto':
        mode='radial' if len(ids)>3 and max(degree.values(),default=0)>=len(ids)-1 else 'layered'
    if mode=='radial' and len(ids)>1:
        hub=min(ids,key=lambda x:(-degree[x],x));others=[x for x in ids if x!=hub]
        radius=max(cw,ch)*max(1.3,len(others)/(2*math.pi))*1.3
        pts={hub:(radius,radius)}
        for i,g in enumerate(others):
            angle=2*math.pi*i/len(others)-math.pi/2
            pts[g]=(round(radius+radius*math.cos(angle)),round(radius+radius*math.sin(angle)))
    elif mode=='linear':
        r=ranks(ids,edges);ordered=sorted(ids,key=lambda x:(r[x],x))
        pts={g:(i*cw,0) for i,g in enumerate(ordered)}
    else:
        r=ranks(ids,edges);layers=defaultdict(list)
        for g in ids:layers[r[g]].append(g)
        # A strongly connected cluster remains readable as a compact grid.
        pts={}
        for layer,gs in sorted(layers.items()):
            for i,g in enumerate(gs):pts[g]=(layer*cw,i*ch)
    minx=min(x for x,y in pts.values());miny=min(y for x,y in pts.values())
    return {g:(x-minx,y-miny) for g,(x,y) in pts.items()},mode


def _route(start, end, obstacles, used):
    xs=sorted({start[0],end[0],*(max(0,r['x']-offset) for r in obstacles for offset in (0,24,48)),*(r['x']+r['w']+offset for r in obstacles for offset in (0,24,48)),0})
    ys=sorted({start[1],end[1],*(max(0,r['y']-offset) for r in obstacles for offset in (0,24,48)),*(r['y']+r['h']+offset for r in obstacles for offset in (0,24,48)),0})
    xs.append(max(xs)+40);ys.append(max(ys)+40)
    xi={v:i for i,v in enumerate(xs)};yi={v:i for i,v in enumerate(ys)}
    initial=(xi[start[0]],yi[start[1]],0);goal=(xi[end[0]],yi[end[1]])
    queue=[(0,0,initial)];distance={initial:0};prev={};clear={}
    while queue:
        _,cost,state=heapq.heappop(queue)
        if cost!=distance[state]:continue
        x,y,direction=state
        if (x,y)==goal:
            path=[]
            while True:
                path.append((xs[state[0]],ys[state[1]]))
                if state==initial:break
                state=prev[state]
            return list(reversed(path))
        for dx,dy,dd in ((1,0,1),(-1,0,1),(0,1,2),(0,-1,2)):
            xx,yy=x+dx,y+dy
            if not(0<=xx<len(xs) and 0<=yy<len(ys)):continue
            a=(xs[x],ys[y]);b=(xs[xx],ys[yy]);key=tuple(sorted((a,b)))
            if key not in clear:clear[key]=not any(hits(a,b,r) for r in obstacles)
            if not clear[key]:continue
            penalty=0
            for c,d in used:
                if a[1]==b[1]==c[1]==d[1]:
                    penalty+=max(0,min(max(a[0],b[0]),max(c[0],d[0]))-max(min(a[0],b[0]),min(c[0],d[0])))*5
                elif a[0]==b[0]==c[0]==d[0]:
                    penalty+=max(0,min(max(a[1],b[1]),max(c[1],d[1]))-max(min(a[1],b[1]),min(c[1],d[1])))*5
                elif a[1]==b[1] and c[0]==d[0] and min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(c[1],d[1])<a[1]<max(c[1],d[1]):penalty+=180
                elif a[0]==b[0] and c[1]==d[1] and min(c[0],d[0])<a[0]<max(c[0],d[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1]):penalty+=180
            nc=cost+abs(a[0]-b[0])+abs(a[1]-b[1])+(28 if direction and direction!=dd else 0)+penalty
            nxt=(xx,yy,dd)
            if nc<distance.get(nxt,float('inf')):
                distance[nxt]=nc;prev[nxt]=state
                h=abs(b[0]-end[0])+abs(b[1]-end[1])
                heapq.heappush(queue,(nc+h,nc,nxt))
    raise ModelError('No safe orthogonal route; split this architecture into smaller views')


def simplify(points):
    out=[]
    for p in points:
        if out and p==out[-1]:continue
        while len(out)>=2 and (out[-2][0]==out[-1][0]==p[0] or out[-2][1]==out[-1][1]==p[1]):out.pop()
        out.append(p)
    return out


def layout(model):
    warnings=validate(model)
    nodes={};groups={};bounds={};headers=[]
    bygroup=defaultdict(list)
    node_ids=[n['id'] for n in model['nodes']]
    node_rank=ranks(node_ids,placement_edges(model,{n:n for n in node_ids}))
    for n in sorted(model['nodes'],key=lambda n:(node_rank[n['id']],n['id'])):bygroup[n['group']].append(n)
    gmeta={g['id']:g for g in model['groups']}
    owner={n['id']:n['group'] for n in model['nodes']}
    edges=placement_edges(model,owner)
    # Layout each boundary independently, so enclosing rectangles cannot claim unrelated groups.
    regions=defaultdict(list)
    for g in model['groups']:regions[g['boundary']].append(g['id'])
    cursor_y=100;chosen=[]
    bmeta={b['id']:b for b in model['boundaries']}
    for region,ids in sorted(regions.items(),key=lambda kv:kv[0] or ''):
        specs={}
        for g in ids:
            heading=wrap(gmeta[g]['label'],32)
            gh=36+22*len(heading);nh=[]
            for n in bygroup[g]:
                lines=wrap(n['label'],26);body=wrap(n['responsibility'],30)
                nh.append((n,lines,body,50+22*len(lines)+19*len(body)))
            specs[g]=(gh,nh,gh+sum(x[3]+36 for x in nh)+58)
        cw=420;ch=max(s[2] for s in specs.values())+120
        bh=40+20*len(wrap(bmeta[region]['label'],32)) if region else 40
        points,mode=positions(ids,[(owner[e['source']],owner[e['target']]) for e in model['relations']] if model['layout']=='radial' else edges,model['layout'],cw,ch);chosen.append(mode)
        for g in sorted(ids):
            x,y=points[g];x+=80;y+=cursor_y+bh+20
            gh,nh,height=specs[g]
            groups[g]={'x':x,'y':y,'w':320,'h':height,'header_h':gh,'lines':wrap(gmeta[g]['label'],32)}
            headers.append({'x':x,'y':y,'w':320,'h':gh-6})
            ny=y+gh+50
            for n,lines,body,h in nh:
                nodes[n['id']]={'x':x+30,'y':ny,'w':260,'h':h,'lines':lines,'body':body}
                ny+=h+36
        right=max(groups[g]['x']+groups[g]['w'] for g in ids)
        bottom=max(groups[g]['y']+groups[g]['h'] for g in ids)
        if region is not None:
            bounds[region]={'x':52,'y':cursor_y,'w':right-24,'h':bottom-cursor_y+28}
            headers.append({'x':52,'y':cursor_y,'w':right-24,'h':bh-6})
        cursor_y=bottom+160
    obstacles=[{'x':r['x']-12,'y':r['y']-12,'w':r['w']+24,'h':r['h']+24} for r in [*nodes.values(),*headers]]
    # Sort incident edges by peer position before assigning distinct boundary ports.
    # This prevents arbitrary ID order from forcing crossings near a hub.
    incidents=defaultdict(list);ends={};routes={};used=[]
    for edge in model['relations']:
        a=nodes[edge['source']];b=nodes[edge['target']]
        ax,ay=a['x']+a['w']/2,a['y']+a['h']/2
        bx,by=b['x']+b['w']/2,b['y']+b['h']/2
        if edge['source']==edge['target']:sa,sb='right','left'
        elif abs(by-ay)>abs(bx-ax)*1.25:sa,sb=('bottom','top') if by>ay else ('top','bottom')
        else:sa,sb=('right','left') if bx>=ax else ('left','right')
        for k,ident,side,peer in [('src',edge['source'],sa,(bx,by)),('dst',edge['target'],sb,(ax,ay))]:
            incidents[(ident,side)].append((peer[1] if side in ('left','right') else peer[0],edge['id'],k))
    for (ident,side),members in incidents.items():
        rect=nodes[ident];horizontal=side in ('left','right')
        span=rect['h'] if horizontal else rect['w']
        step=min(14,(span-32)/max(1,len(members)-1))
        if step<6:raise ModelError('Too many relations on one node; split the view')
        for i,(_,eid,k) in enumerate(sorted(members)):
            offset=(i-(len(members)-1)/2)*step
            if horizontal:
                x=rect['x']+(rect['w'] if side=='right' else 0);y=rect['y']+rect['h']/2+offset
                stub=(x+(22 if side=='right' else -22),y)
            else:
                x=rect['x']+rect['w']/2+offset;y=rect['y']+(rect['h'] if side=='bottom' else 0)
                stub=(x,y+(22 if side=='bottom' else -22))
            ends[(eid,k)]=((x,y),stub)
    for edge in sorted(model['relations'],key=lambda e:e['id']):
        start,stub1=ends[(edge['id'],'src')];end,stub2=ends[(edge['id'],'dst')]
        route=_route(stub1,stub2,obstacles,used)
        clean=simplify(route)
        used.extend(zip(clean,clean[1:]))
        routes[edge['id']]={'points':simplify([start,*route,end])}
    # Diagnose crossing/overlap; do not silently omit any relation.
    crossings=set();shared=set()
    items=list(routes.items())
    for i,(eid,r) in enumerate(items):
        for fid,s in items[i+1:]:
            for a,b in zip(r['points'],r['points'][1:]):
                for c,d in zip(s['points'],s['points'][1:]):
                    if a[1]==b[1] and c[0]==d[0] and min(a[0],b[0])<c[0]<max(a[0],b[0]) and min(c[1],d[1])<a[1]<max(c[1],d[1]):crossings.add((eid,fid))
                    if a[0]==b[0] and c[1]==d[1] and min(c[0],d[0])<a[0]<max(c[0],d[0]) and min(a[1],b[1])<c[1]<max(a[1],b[1]):crossings.add((eid,fid))
                    if a[0]==b[0]==c[0]==d[0] and max(min(a[1],b[1]),min(c[1],d[1]))<min(max(a[1],b[1]),max(c[1],d[1])):shared.add((eid,fid))
                    if a[1]==b[1]==c[1]==d[1] and max(min(a[0],b[0]),min(c[0],d[0]))<min(max(a[0],b[0]),max(c[0],d[0])):shared.add((eid,fid))
    if crossings:warnings.append({'code':'edge-crossings','pairs':sorted(crossings)})
    if shared:warnings.append({'code':'shared-edge-segments','pairs':sorted(shared)})
    labels=[]
    for i,(eid,r) in enumerate(items,1):
        r['number']=i;r['badge']=None
        for a,b in sorted(zip(r['points'],r['points'][1:]),key=lambda ab:-math.dist(*ab)):
            if math.dist(a,b)<(48 if a[1]==b[1] else 30):continue
            for t in (0.5,0.3,0.7):
                box={'x':a[0]+t*(b[0]-a[0])-19,'y':a[1]+t*(b[1]-a[1])-11,'w':38,'h':22}
                if any(overlaps(box,o,3) for o in [*nodes.values(),*headers,*labels]):continue
                if any(hits(c,d,box) for fid,s in items if fid!=eid for c,d in zip(s['points'],s['points'][1:])):continue
                r['badge']=box;labels.append(box);break
            if r['badge']:break
        if r['badge'] is None:warnings.append({'code':'edge-badge-in-ledger-only','id':eid})
    all_rects=[*groups.values(),*bounds.values()]
    pts=[p for r in routes.values() for p in r['points']]
    width=max([r['x']+r['w'] for r in all_rects]+[x for x,y in pts])+80
    height=max([r['y']+r['h'] for r in all_rects]+[y for x,y in pts])+60
    return {'nodes':nodes,'groups':groups,'boundaries':bounds,'routes':routes,'width':width,'height':height,'modes':chosen,'warnings':warnings}
