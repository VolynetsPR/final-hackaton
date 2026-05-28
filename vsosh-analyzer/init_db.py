import os, glob, shutil
from db import DB_PATH, get_connection, init_schema
from parser_utils import parse_html_file
from school_utils import _load as load_school_rows

UPLOADS = os.path.join(os.path.dirname(__file__), 'uploads')

def recreate_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    con = get_connection()
    init_schema(con)
    return con

def participant_id(con, row):
    con.execute('''INSERT OR IGNORE INTO participants(full_name, region, class_num)
                   VALUES(?,?,?)''', (row['full_name'], row['region'], row['class_num']))
    
    con.execute('''UPDATE participants SET region=?, class_num=? WHERE full_name=?''',
                (row['region'], row['class_num'], row['full_name']))
    
    return con.execute('SELECT id FROM participants WHERE full_name=?', (row['full_name'],)).fetchone()['id']

def load_html(con):
    files = sorted(glob.glob(os.path.join(UPLOADS, '*.html')), key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
    for path in files:
        snap = parse_html_file(path)
        cur = con.execute('''INSERT OR REPLACE INTO snapshots(tour, minute, status, title, problem_count, source_name)
                             VALUES(?,?,?,?,?,?)''', (snap['tour'], snap['minute'], snap['status'], snap['title'], snap['problem_count'], snap['source_name']))
        sid = cur.lastrowid or con.execute('SELECT id FROM snapshots WHERE tour=? AND minute=?',(snap['tour'], snap['minute'])).fetchone()['id']
        con.execute('DELETE FROM results WHERE snapshot_id=?', (sid,))
        for r in snap['rows']:
            pid = participant_id(con, r)
            s = r['scores']
            con.execute('''INSERT INTO results(snapshot_id, participant_id, rank_text, rank_start, rank_end,
                         p1,p2,p3,p4,p5,p6,p7,p8,total) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (sid, pid, r['rank_text'], r['rank_start'], r['rank_end'], *s, r['total']))
    con.commit()

def load_regional_csv(con):
    for nm, school, region, raw in load_school_rows():
        con.execute('INSERT INTO regional_students(city, name, school) VALUES(?,?,?)', (region, raw, school))
    for p in con.execute('SELECT id, full_name FROM participants').fetchall():
        school, school_region = get_school(p['full_name'])
        if school:
            con.execute('UPDATE participants SET school=?, school_region=? WHERE id=?', (school, school_region, p['id']))
    con.commit()

def copy_static():
    os.makedirs('static', exist_ok=True)
    src = os.path.join(UPLOADS, 'standings2.css')
    if os.path.exists(src): shutil.copy(src, os.path.join('static', 'standings2.css'))

def main():
    con = recreate_database()
    copy_static()
    load_html(con)
    load_regional_csv(con)
    
    con.close()
    print('База данных создана:', DB_PATH)

if __name__ == '__main__':
    main()
