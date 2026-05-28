import os, io, base64
from flask import Flask, render_template, request, redirect, url_for, send_file
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from db import DB_PATH, get_connection
from services import (region_stats, school_stats, regions_with_min, schools_with_min,
    select_snapshot, filtered_result_rows, PROBLEM_HEADERS, SCORE_FIELDS, diploma_map,
    participant_info, latest_snapshot_id, rank_ranges)

app = Flask(__name__)

CRITERIA = {
    'participants': 'Участники', 'prizes': 'Призёры',
    'winners': 'Победители', 'diplomas': 'Дипломы'
}
CLASS_FILTERS = {
    'all':'Все участники','11':'11 класс','10':'10 класс','9':'9 класс',
    '10_down':'10 класс и младше','9_down':'9 класс и младше','8_down':'8 класс и младше'
}
TOUR_MODES = {'first':1, 'second':2, 'both':3}

@app.before_request
def ensure_db():
    if not os.path.exists(DB_PATH) and request.endpoint != 'static':
        # удобство для первого запуска; при проверке БД создаётся init_db.py отдельно
        try:
            import init_db; init_db.main()
        except Exception:
            pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/regions')
def regions():
    criterion = request.args.get('criterion','participants')
    if criterion not in CRITERIA: criterion='participants'
    return render_template('stats_regions.html', rows=region_stats(criterion), criteria=CRITERIA, current=criterion)

@app.route('/schools')
def schools():
    criterion = request.args.get('criterion','participants')
    if criterion not in CRITERIA: criterion='participants'
    return render_template('stats_schools.html', rows=school_stats(criterion), criteria=CRITERIA, current=criterion)

@app.route('/results')
def results_form():
    selected_region = request.args.get('region','all')
    return render_template('results_form.html', regions=regions_with_min(3), schools=schools_with_min(selected_region,3),
                           selected_region=selected_region, class_filters=CLASS_FILTERS)

@app.route('/api/schools')
def api_schools():
    region = request.args.get('region','all')
    rows = schools_with_min(region,3) if region in ('Москва','Санкт-Петербург') else []
    return {'schools':[{'school':r['school'], 'region':r['school_region']} for r in rows]}

@app.route('/results/table')
def results_table():
    tour_choice=request.args.get('tour','both')
    mode=TOUR_MODES.get(tour_choice,3)
    time_mode=request.args.get('time_mode','final')
    minute=None
    if time_mode == 'at':
        raw=request.args.get('minute','')
        try:
            minute=int(raw)
            if not (0 <= minute <= 299): raise ValueError
        except Exception:
            return render_template('message.html', title='Некорректный момент времени',
                message='Введите целое число от 0 до 299 — количество минут с начала выбранного тура.'), 400
    con=get_connection()
    snap=select_snapshot(con, tour_choice, time_mode, minute)
    if not snap:
        con.close(); return render_template('message.html', title='Результаты ещё не сформированы', message='Результаты ещё не сформированы')
    rows=filtered_result_rows(con, snap['id'], mode, request.args.get('class_filter','all'),
                              request.args.get('region','all'), request.args.get('school','all'))
    diplomas=diploma_map(con)
    highlight=request.args.get('style','clean') == 'diplomas'
    con.close()
    title = f"Результаты: {dict(first='первый тур', second='второй тур', both='оба тура').get(tour_choice)}"
    return render_template('standings.html', rows=rows, headers=PROBLEM_HEADERS[mode], fields=SCORE_FIELDS[mode],
                           title=title, snap=snap, diplomas=diplomas, highlight=highlight)

@app.route('/participant/<int:pid>')
def participant(pid):
    info=participant_info(pid)
    if not info: return render_template('message.html', title='Не найдено', message='Участник не найден'), 404
    return render_template('participant.html', info=info)

def chart_points(pid, kind, mode):
    con=get_connection(); points=[]
    if mode in ('first','both'):
        for s in con.execute('SELECT * FROM snapshots WHERE tour=1 ORDER BY minute'):
            r=con.execute('SELECT * FROM results WHERE snapshot_id=? AND participant_id=?',(s['id'],pid)).fetchone()
            if not r: continue
            score=sum(r[f] or 0 for f in SCORE_FIELDS[1])
            y=score
            if kind=='rank':
                allr=[{'score':sum(rr[f] or 0 for f in SCORE_FIELDS[1])} for rr in con.execute('SELECT p1,p2,p3,p4 FROM results WHERE snapshot_id=?',(s['id'],))]
                y=rank_ranges(allr,'score')[score][1]
            points.append((s['minute'], y))
    if mode in ('second','both'):
        for s in con.execute('SELECT * FROM snapshots WHERE tour=2 ORDER BY minute'):
            r=con.execute('SELECT * FROM results WHERE snapshot_id=? AND participant_id=?',(s['id'],pid)).fetchone()
            if not r: continue
            fields = SCORE_FIELDS[2] if mode=='second' else SCORE_FIELDS[3]
            score=sum(r[f] or 0 for f in fields)
            y=score
            if kind=='rank':
                sel=','.join(fields)
                allr=[{'score':sum(rr[f] or 0 for f in fields)} for rr in con.execute(f'SELECT {sel} FROM results WHERE snapshot_id=?',(s['id'],))]
                y=rank_ranges(allr,'score')[score][1]
            x=s['minute'] if mode=='second' else 300+s['minute']
            points.append((x,y))
    con.close(); return points

@app.route('/participant/<int:pid>/chart/<kind>/<mode>.png')
def chart(pid, kind, mode):
    if kind not in ('score','rank') or mode not in ('first','second','both'):
        return 'bad chart', 400
    pts=chart_points(pid,kind,mode)
    fig, ax = plt.subplots(figsize=(8,3.8), dpi=130)
    if pts:
        x,y=zip(*pts); ax.plot(x,y, marker='o', linewidth=2.2, color='#2b6cb0')
    ax.grid(True, alpha=.25); ax.set_xlabel('Минуты с начала ' + ('олимпиады' if mode=='both' else 'тура'))
    ax.set_ylabel('Баллы' if kind=='score' else 'Место')
    ax.set_title(('Баллы' if kind=='score' else 'Место') + ': ' + {'first':'первый тур','second':'второй тур','both':'оба тура'}[mode])
    if kind=='rank': ax.invert_yaxis()
    fig.tight_layout(); bio=io.BytesIO(); fig.savefig(bio, format='png'); plt.close(fig); bio.seek(0)
    return send_file(bio, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)
