import os, re
from bs4 import BeautifulSoup

PARTY_RE = re.compile(r'^(.*?)\s*\((.*),\s*(\d+)\s*класс\)\s*$')

def parse_rank(rank):
    text = (rank or '').strip().replace('–','-').replace('—','-')
    nums = [int(x) for x in re.findall(r'\d+', text)]
    if not nums:
        return None, None
    return nums[0], nums[-1]

def score_from_cell(cell):
    s = cell.get_text('', strip=True).replace('\xa0','')
    if not s or s == '.':
        return 0
    m = re.search(r'-?\d+', s)
    return int(m.group()) if m else 0

def parse_html_file(path):
    html = open(path, encoding='utf-8').read()
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h2').get_text(' ', strip=True)
    tour = 1
    if 'Второй тур' in title:
        tour = 2
    minute = int(os.path.splitext(os.path.basename(path))[0])
    status_text = ''
    if soup.find('p'):
        status_text = soup.find('p').get_text(' ', strip=True)
    problems = len(soup.select('thead th.problem'))
    rows = []
    for tr in soup.select('tbody tr'):
        tds = tr.find_all('td')
        
        if len(tds) < 3: 
            continue
        rank_text = tds[0].get_text('', strip=True)
        party = tds[1].get_text(' ', strip=True)
        m = PARTY_RE.match(party)
        if not m:
            continue
        full_name, region, class_num = m.group(1).strip(), m.group(2).strip(), int(m.group(3))
        scores = [score_from_cell(td) for td in tds[2:2 + problems]]
        while len(scores) < 8:
            scores.append(0)
        total = score_from_cell(tds[-1])
        rs, re_ = parse_rank(rank_text)
        rows.append(dict(full_name=full_name, region=region, class_num=class_num,
                         rank_text=rank_text, rank_start=rs, rank_end=re_, scores=scores[:8], total=total))
    return dict(tour=tour, minute=minute, title=title, status=status_text,
                problem_count=problems, source_name=os.path.basename(path), rows=rows)
