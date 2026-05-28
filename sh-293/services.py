from collections import Counter, defaultdict
from db import get_connection

DIPLOMA_INVITED = 383
WINNERS_LIMIT = int(DIPLOMA_INVITED * 0.08)
DIPLOMAS_LIMIT = int(DIPLOMA_INVITED * 0.45)
MIN_DIPLOMA_SCORE = 400

SCORE_FIELDS = {1: ['p1','p2','p3','p4'], 2: ['p5','p6','p7','p8'], 3: ['p1','p2','p3','p4','p5','p6','p7','p8']}
PROBLEM_HEADERS = {1: ['1','2','3','4'], 2: ['5','6','7','8'], 3: ['1','2','3','4','5','6','7','8']}

def latest_snapshot_id(con, tour):
    r = con.execute('SELECT id FROM snapshots WHERE tour=? ORDER BY minute DESC LIMIT 1', (tour,)).fetchone()
    return r['id'] if r else None

def select_snapshot(con, tour_choice, time_mode='final', minute=None):
    tour = 2
    if tour_choice == 'first':
        tour = 1
    if time_mode == 'at':
        q = 'SELECT * FROM snapshots WHERE tour=? AND minute<=? ORDER BY minute DESC LIMIT 1'
        return con.execute(q, (tour, int(minute))).fetchone()
    return con.execute('SELECT * FROM snapshots WHERE tour=? ORDER BY minute DESC LIMIT 1', (tour,)).fetchone()

def score_expr(alias, mode):
    fields = SCORE_FIELDS[mode]
    return ' + '.join([f'COALESCE({alias}.{f},0)' for f in fields])

def rank_ranges(rows, key='score'):
    sorted_scores = sorted([r[key] for r in rows], reverse=True)
    positions = {}
    i = 0
    while i < len(sorted_scores):
        val = sorted_scores[i]
        j = i
        while j < len(sorted_scores) and sorted_scores[j] == val: j += 1
        positions[val] = (i+1, j)
        i = j
    return {val: (f'{a}-{b}' if a != b else str(a), a, b) for val,(a,b) in positions.items()}

def diploma_map(con):
    sid = latest_snapshot_id(con, 2)
    if not sid: return {}
    rows = con.execute('''SELECT p.id, (r.p1+r.p2+r.p3+r.p4+r.p5+r.p6+r.p7+r.p8) score
                          FROM results r JOIN participants p ON p.id=r.participant_id
                          WHERE r.snapshot_id=? ORDER BY score DESC, p.full_name''', (sid,)).fetchall()
    res = {}
    for idx, r in enumerate(rows, 1):
        if r['score'] < MIN_DIPLOMA_SCORE: continue
        if idx <= WINNERS_LIMIT: res[r['id']] = 'winner'
        elif idx <= DIPLOMAS_LIMIT: res[r['id']] = 'prize'
    return res

def filtered_result_rows(con, snapshot_id, mode, class_filter='all', region='all', school='all'):
    rows = []
    for r in con.execute('''SELECT p.*, r.* FROM results r JOIN participants p ON p.id=r.participant_id
                            WHERE r.snapshot_id=?''', (snapshot_id,)).fetchall():
        cls = r['class_num']
        if(class_filter.isnumeric() and int(class_filter) != cls):
            continue
        if class_filter == '10_down' and cls > 10:
            continue
        if class_filter == '9_down' and cls > 9:
            continue
        if class_filter == '8_down' and cls > 8:
            continue
        if region != 'all' and r['region'] != region:
            continue
        if school != 'all' and (r['school'] or '') != school:
            continue
        score = sum(r[f] or 0 for f in SCORE_FIELDS[mode])
        rows.append(dict(r, score=score))
    ranks = rank_ranges(rows, 'score')
    for r in rows:
        r['rank'] = ranks[r['score']][0]
    return sorted(rows, key=lambda x: (-x['score'], x['full_name']))

def criteria_value(status, criterion):
    if criterion == 'participants': return True
    if criterion == 'winners': return status == 'winner'
    if criterion == 'prizes': return status == 'prize'
    if criterion == 'diplomas': return status in ('winner','prize')
    return False

def ranked_counts(counter):
    items = sorted([(k,v) for k,v in counter.items() if v > 0], key=lambda x: (-x[1], x[0]))
    out=[]; i=0
    while i < len(items):
        v=items[i][1]; j=i
        while j < len(items) and items[j][1] == v: j += 1
        place = f'{i+1}-{j}' if i+1 != j else str(i+1)
        for name,val in items[i:j]: out.append((place,name,val))
        i=j
    return out

def region_stats(criterion):
    con=get_connection(); d=diploma_map(con); sid=latest_snapshot_id(con,2)
    counter=Counter()
    for p in con.execute('''SELECT DISTINCT p.id, p.region FROM participants p JOIN results r ON r.participant_id=p.id WHERE r.snapshot_id=?''',(sid,)):
        if criteria_value(d.get(p['id']), criterion):
            counter[p['region']] += 1
    con.close(); return ranked_counts(counter)

def school_stats(criterion):
    con=get_connection(); d=diploma_map(con); sid=latest_snapshot_id(con,2)
    counter=Counter(); regions={}
    for p in con.execute('''SELECT DISTINCT p.id, p.school, p.school_region FROM participants p JOIN results r ON r.participant_id=p.id
                            WHERE r.snapshot_id=? AND p.school IS NOT NULL AND p.school_region IN ('Москва','Санкт-Петербург')''',(sid,)):
        key=(p['school'],p['school_region']); regions[p['school']]=p['school_region']
        if criteria_value(d.get(p['id']), criterion):
            counter[key] += 1
    items=sorted([(k,v) for k,v in counter.items() if v>0], key=lambda x:(-x[1], x[0][0], x[0][1]))
    out = []
    i = 0
    while i < len(items):
        v = items[i][1]
        j = i
        while j < len(items) and items[j][1] == v:
            j+=1
        place=f'{i+1}-{j}' if i + 1 != j else str(i+1)
        for (school, reg), val in items[i:j]:
            out.append((place, school, reg, val))
        i = j
    con.close()
    return out

def regions_with_min(n=3):
    con = get_connection()
    sid = latest_snapshot_id(con,2)
    rows = con.execute('''SELECT p.region, COUNT(*) c FROM participants p JOIN results r ON r.participant_id=p.id
                        WHERE r.snapshot_id=? GROUP BY p.region HAVING c>=? ORDER BY p.region''',(sid,n)).fetchall()
    con.close()
    return [r['region'] for r in rows]

def schools_with_min(region=None, n=3):
    con = get_connection(); sid=latest_snapshot_id(con,2)
    params = [sid]
    where="p.school IS NOT NULL AND p.school_region IN ('Москва','Санкт-Петербург')"
    if region in ('Москва','Санкт-Петербург'):
        where += ' AND p.school_region=?'
        params.append(region)
    params.append(n)
    rows=con.execute(f'''SELECT p.school, p.school_region, COUNT(*) c FROM participants p JOIN results r ON r.participant_id=p.id
                         WHERE r.snapshot_id=? AND {where} GROUP BY p.school,p.school_region HAVING c>=? ORDER BY p.school''', params).fetchall()
    con.close(); return rows

def participant_info(pid):
    con=get_connection()
    p=con.execute('SELECT * FROM participants WHERE id=?',(pid,)).fetchone()
    if not p: 
        con.close()
        return None
    first_sid=latest_snapshot_id(con,1); both_sid=latest_snapshot_id(con,2)
    r1=con.execute('SELECT * FROM results WHERE snapshot_id=? AND participant_id=?',(first_sid,pid)).fetchone() if first_sid else None
    r2=con.execute('SELECT * FROM results WHERE snapshot_id=? AND participant_id=?',(both_sid,pid)).fetchone() if both_sid else None
    all_rows=[]
    if r2:
        for rr in con.execute('SELECT participant_id,p1,p2,p3,p4,p5,p6,p7,p8 FROM results WHERE snapshot_id=?',(both_sid,)):
            all_rows.append({'pid':rr['participant_id'],'total':sum(rr[f] or 0 for f in SCORE_FIELDS[3]),'second':sum(rr[f] or 0 for f in SCORE_FIELDS[2])})
    first_rows=[]
    if r1:
        for rr in con.execute('SELECT participant_id,p1,p2,p3,p4 FROM results WHERE snapshot_id=?',(first_sid,)):
            first_rows.append({'pid':rr['participant_id'],'first':sum(rr[f] or 0 for f in SCORE_FIELDS[1])})
    def get_rank(rows,key):
        score=next((x[key] for x in rows if x['pid']==pid),0); ranks=rank_ranges(rows,key); return score, ranks.get(score,('—',None,None))[0]
    first_score, first_rank = get_rank(first_rows,'first') if first_rows else (0,'—')
    second_score, second_rank = get_rank(all_rows,'second') if all_rows else (0,'—')
    total_score, total_rank = get_rank(all_rows,'total') if all_rows else (0,'—')
    scores=[(r2 or r1)[f'p{i}'] if (r2 or r1) else 0 for i in range(1,9)]
    con.close()
    return dict(participant=p, scores=scores, first_score=first_score, second_score=second_score,
                total_score=total_score, first_rank=first_rank, second_rank=second_rank, total_rank=total_rank)
