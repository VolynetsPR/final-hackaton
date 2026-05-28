import csv, os, re
UPLOADS = os.path.join(os.path.dirname(__file__), 'uploads')
MOSCOW_FILE = os.path.join(UPLOADS, 'Результаты регионального этапа в Москве.csv')
SPB_FILE = os.path.join(UPLOADS, 'Результаты регионального этапа в Санкт-Петербурге.csv')
_cache = None

def normalize_name(name):
    return ' '.join((name or '').replace('ё','е').replace('Ё','Е').lower().split())

def _load():
    global _cache
    if _cache is not None: return _cache
    rows = []
    if os.path.exists(MOSCOW_FILE):
        with open(MOSCOW_FILE, encoding='cp1251', newline='') as f:
            for r in csv.DictReader(f, delimiter=';'):
                nm = (r.get('Участник') or '').strip()
                school = (r.get('Школа') or '').strip()
                if nm and school:
                    rows.append((normalize_name(nm), school, 'Москва', nm))
    if os.path.exists(SPB_FILE):
        with open(SPB_FILE, encoding='cp1251', newline='') as f:
            for r in csv.DictReader(f, delimiter=';'):
                raw = (r.get('Участник') or '').strip()
                m = re.match(r'(.+?)\s*\((.*?),\s*\d+\s*класс\)', raw)
                if m:
                    nm, school_code = m.group(1).strip(), m.group(2).strip()
                    school = f'Школа № {school_code}' if school_code.isdigit() else school_code
                    rows.append((normalize_name(nm), school, 'Санкт-Петербург', nm))
    _cache = rows
    return rows

def get_school(full_name):
    """Возвращает (школа, регион школы) по ФИО участника или (None, None)."""
    q = normalize_name(full_name)
    parts = q.split()
    for nm, school, region, _ in _load():
        # Москва в протоколе часто без отчества: сравниваем по началу ФИО/первым двум словам.
        if q == nm or q.startswith(nm + ' ') or (len(parts) >= 2 and nm == ' '.join(parts[:2])):
            return school, region
    return None, None
