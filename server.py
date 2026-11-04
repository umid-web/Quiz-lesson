"""Local SQLite or hosted PostgreSQL selected by DATABASE_URL."""
import csv, hashlib, hmac, io, json, os, secrets, sqlite3, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

ROOT = Path(__file__).resolve().parent
DB = os.environ.get('QUIZ_DB', str(ROOT / 'data' / 'quiz.sqlite3'))
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
LOCK = threading.RLock()
DURATION = 30
BANK_SIZE = 50
TEST_SIZE = 15

class Database:
    """Small compatibility layer for the application's fixed SQL statements."""
    def __init__(self, connection, postgres=False):
        self.raw = connection
        self.postgres = postgres
    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace('?', '%s')
        return self.raw.execute(sql, params)
    def executescript(self, sql):
        # Schema statements have no semicolons inside strings.
        for statement in sql.split(';'):
            if statement.strip():
                self.execute(statement)
    def __enter__(self):
        return self
    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()

class Record(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)

def record_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Record(zip(names, values))

def connect():
    if DATABASE_URL:
        try:
            import psycopg
        except ImportError:
            raise RuntimeError('PostgreSQL uchun: pip install -r requirements.txt') from None
        return Database(psycopg.connect(DATABASE_URL, row_factory=record_factory,
                                       connect_timeout=15), postgres=True)
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return Database(c)

def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 250000).hex()

def initialize():
    if not DATABASE_URL:
        Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        if not DATABASE_URL:
            c.execute('PRAGMA journal_mode=WAL')
        schema = '''
        CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,token TEXT UNIQUE NOT NULL,name TEXT NOT NULL,
          topic TEXT NOT NULL,questions TEXT NOT NULL,answers TEXT NOT NULL,idx INTEGER NOT NULL,
          deadline REAL NOT NULL,started REAL NOT NULL,finished REAL,events INTEGER NOT NULL DEFAULT 0);
        '''
        c.executescript(schema.replace(' REAL', ' DOUBLE PRECISION') if DATABASE_URL else schema)
        if DATABASE_URL:
            c.execute("ALTER TABLE attempts ADD COLUMN IF NOT EXISTS subject TEXT NOT NULL DEFAULT ''")
        elif 'subject' not in [row[1] for row in c.execute('PRAGMA table_info(attempts)')]:
            c.execute("ALTER TABLE attempts ADD COLUMN subject TEXT NOT NULL DEFAULT ''")
        if not c.execute("SELECT 1 FROM config WHERE key='admin'").fetchone():
            username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', 'admin')
            password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
            if not password or len(password) < 10:
                raise SystemExit('Avval python setup_admin.py buyrug‘i bilan admin yarating (parol kamida 10 belgi).')
            salt = secrets.token_hex(16)
            c.execute('INSERT INTO config VALUES (?,?)', ('admin',json.dumps(dict(username=username,salt=salt,hash=digest(password,salt)))))
        if not c.execute("SELECT 1 FROM config WHERE key='quiz'").fetchone():
            c.execute('INSERT INTO config VALUES (?,?)', ('quiz',(ROOT/'questions.example.json').read_text(encoding='utf-8')))

def validate_quiz(q):
    if not isinstance(q,dict) or not isinstance(q.get('title'),str) or not 1 <= len(q['title'].strip()) <= 160:
        raise ValueError('Mavzu nomini kiriting (1–160 belgi).')
    if not isinstance(q.get('questions'),list) or len(q['questions']) != BANK_SIZE:
        raise ValueError('Bankda aniq 50 ta savol bo‘lishi kerak.')
    if not isinstance(q.get('subject'),str) or not 1 <= len(q['subject'].strip()) <= 160:
        raise ValueError('Fan nomini kiriting (1–160 belgi).')
    if len({x.get('text','').strip() for x in q['questions'] if isinstance(x,dict) and isinstance(x.get('text'),str)}) != BANK_SIZE:
        raise ValueError('50 ta savol matni takrorlanmasligi kerak.')
    for x in q['questions']:
        if not isinstance(x,dict) or not isinstance(x.get('text'),str) or not 1 <= len(x['text'].strip()) <= 2000:
            raise ValueError('Savol matni noto‘g‘ri.')
        if not isinstance(x.get('options'),list) or len(x['options']) != 4 or any(not isinstance(v,str) or not 1<=len(v.strip())<=600 for v in x['options']):
            raise ValueError('Har savolda 4 ta bo‘sh bo‘lmagan variant kerak.')
        if type(x.get('correct')) is not int or x['correct'] not in range(4):
            raise ValueError('To‘g‘ri javob indeksi 0, 1, 2 yoki 3 bo‘lishi kerak.')
    return q

def advance(c, a, now):
    a = dict(a)
    answers = json.loads(a['answers'])
    while a['idx'] < 15 and now >= a['deadline']:
        answers.append(None)
        a['idx'] += 1
        a['deadline'] += DURATION
    if a['idx'] == 15 and a['finished'] is None:
        a['finished'] = min(now,a['deadline'] - DURATION)
    a['answers'] = json.dumps(answers)
    c.execute('UPDATE attempts SET answers=?,idx=?,deadline=?,finished=? WHERE id=?',
              (a['answers'],a['idx'],a['deadline'],a['finished'],a['id']))
    return a

def score(a):
    questions, answers = json.loads(a['questions']),json.loads(a['answers'])
    return sum(v == questions[i]['correct'] for i,v in enumerate(answers))

def public_attempt(a):
    result = dict(id=a['id'],name=a['name'],topic=a['topic'],subject=a['subject'],index=a['idx'],total=15,
                  deadline=a['deadline'],serverTime=time.time(),finished=a['finished'] is not None)
    if result['finished']:
        result.update(score=score(a),percent=round(score(a)/15*100))
    else:
        q = json.loads(a['questions'])[a['idx']]
        result['question'] = dict(text=q['text'],options=q['options'])
    return result

class Handler(BaseHTTPRequestHandler):
    server_version = 'QuizServer'
    def log_message(self, fmt, *args):
        # Never log attempt tokens or request bodies.
        pass
    def send(self, code, data, mime='application/json; charset=utf-8', cookie=None):
        body = json.dumps(data,ensure_ascii=False).encode() if mime.startswith('application/json') else data
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)
    def cookies(self):
        c = SimpleCookie()
        try: c.load(self.headers.get('Cookie',''))
        except Exception: return {}
        return {k:v.value for k,v in c.items()}
    def cookie(self,key,value,age):
        return f'{key}={value}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}' + ('; Secure' if os.environ.get('COOKIE_SECURE')=='1' else '')
    def admin(self,c):
        return c.execute('SELECT 1 FROM sessions WHERE token=? AND expires>?',(self.cookies().get('admin',''),time.time())).fetchone() is not None
    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def dispatch(self):
        try:
            with LOCK:
                self.route()
        except ValueError as e: self.send(400,{'error':str(e)})
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            self.send(500,{'error':'Server xatosi. Qayta urinib ko‘ring.'})
    def route(self):
        path = self.path.split('?')[0]
        if self.command == 'GET' and not path.startswith('/api/'):
            files = {'/':'index.html','/admin':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in files: return self.send(404,{'error':'Topilmadi'})
            f = ROOT/'static'/files[path]
            return self.send(200,f.read_bytes(), {'html':'text/html','js':'text/javascript','css':'text/css'}[f.suffix[1:]]+'; charset=utf-8')
        data = {}
        if self.command == 'POST':
            # Require a custom header: cross-origin HTML forms cannot submit API mutations.
            if self.headers.get('X-Quiz-Request') != '1': return self.send(403,{'error':'So‘rov rad etildi'})
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 150000: raise ValueError('So‘rov hajmi noto‘g‘ri')
            try: data = json.loads(self.rfile.read(length))
            except Exception: raise ValueError('JSON noto‘g‘ri')
            if not isinstance(data,dict): raise ValueError('JSON obyekt kerak')
        now = time.time()
        with connect() as c:
            if path == '/api/info' and self.command == 'GET':
                q=json.loads(c.execute("SELECT value FROM config WHERE key='quiz'").fetchone()[0])
                return self.send(200,dict(title=q['title'],subject=q.get('subject',''),bankCount=len(q['questions']),count=TEST_SIZE,seconds=DURATION))
            if path == '/api/login' and self.command == 'POST':
                ip=self.client_address[0]
                failures=self.server.failures.get(ip,[])
                failures=[t for t in failures if now-t<300]
                self.server.failures[ip]=failures
                if len(failures)>=8: return self.send(429,{'error':'Ko‘p urinish. 5 daqiqadan keyin qayta urinib ko‘ring.'})
                a=json.loads(c.execute("SELECT value FROM config WHERE key='admin'").fetchone()[0])
                if len(str(data.get('password','')))>500: raise ValueError('Parol juda uzun')
                if not (hmac.compare_digest(digest(str(data.get('password','')),a['salt']),a['hash']) and hmac.compare_digest(str(data.get('username','')),a['username'])):
                    failures.append(now)
                    return self.send(401,{'error':'Login yoki parol noto‘g‘ri'})
                token=secrets.token_urlsafe(32)
                c.execute('DELETE FROM sessions WHERE expires<?',(now,))
                c.execute('INSERT INTO sessions VALUES (?,?)',(token,now+28800))
                return self.send(200,{'ok':True},cookie=self.cookie('admin',token,28800))
            if path.startswith('/api/admin/'):
                if not self.admin(c): return self.send(401,{'error':'Admin sifatida kiring'})
                if path == '/api/admin/logout' and self.command == 'POST':
                    c.execute('DELETE FROM sessions WHERE token=?',(self.cookies().get('admin',''),))
                    return self.send(200,{'ok':True},cookie=self.cookie('admin','',0))
                if path == '/api/admin/quiz':
                    if self.command == 'POST':
                        validate_quiz(data)
                        c.execute("UPDATE config SET value=? WHERE key='quiz'",(json.dumps(data,ensure_ascii=False),))
                    return self.send(200,json.loads(c.execute("SELECT value FROM config WHERE key='quiz'").fetchone()[0]))
                if path in ('/api/admin/results','/api/admin/export') and self.command == 'GET':
                    rows=[]
                    for a in c.execute('SELECT * FROM attempts ORDER BY started DESC').fetchall():
                        a=advance(c,a,now)
                        rows.append(dict(id=a['id'],name=a['name'],topic=a['topic'],score=score(a),answered=a['idx'],finished=a['finished'] is not None,started=a['started'],events=a['events']))
                    if path.endswith('export'):
                        f=io.StringIO(); w=csv.writer(f); w.writerow(['Ism familiya','Mavzu','Ball (15)','Holat','Boshlanish UTC','Sahifadan chiqishlar'])
                        for r in rows:
                            safe=lambda s: "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
                            w.writerow([safe(r['name']),safe(r['topic']),r['score'],'Yakunlangan' if r['finished'] else 'Jarayonda',time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(r['started'])),r['events']])
                        return self.send(200,('\ufeff'+f.getvalue()).encode(),'text/csv; charset=utf-8')
                    return self.send(200,rows)
            if path == '/api/start' and self.command == 'POST':
                old=c.execute('SELECT * FROM attempts WHERE token=?',(self.cookies().get('attempt',''),)).fetchone()
                if old and old['finished'] is None:
                    return self.send(200,public_attempt(advance(c,old,now)))
                name=' '.join(str(data.get('name','')).split())
                if not 3 <= len(name) <= 100 or len(name.split())<2: raise ValueError('Ism va familiyangizni to‘liq yozing.')
                q=json.loads(c.execute("SELECT value FROM config WHERE key='quiz'").fetchone()[0])
                validate_quiz(q)
                questions=secrets.SystemRandom().sample(q['questions'], TEST_SIZE)
                token=secrets.token_urlsafe(32); aid=secrets.token_hex(12)
                c.execute('INSERT INTO attempts(id,token,name,topic,questions,answers,idx,deadline,started,subject) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (aid,token,name,q['title'],json.dumps(questions), '[]',0,now+DURATION,now,q['subject']))
                a=c.execute('SELECT * FROM attempts WHERE id=?',(aid,)).fetchone()
                return self.send(200,public_attempt(a),cookie=self.cookie('attempt',token,604800))
            if path in ('/api/state','/api/answer','/api/event'):
                a=c.execute('SELECT * FROM attempts WHERE token=?',(self.cookies().get('attempt',''),)).fetchone()
                if not a: return self.send(404,{'error':'Faol test topilmadi'})
                a=advance(c,a,now)
                if path == '/api/event' and self.command == 'POST' and not a['finished']:
                    c.execute('UPDATE attempts SET events=events+1 WHERE id=?',(a['id'],))
                if path == '/api/answer' and self.command == 'POST' and a['finished'] is None:
                    if data.get('index') != a['idx']: return self.send(409,public_attempt(a))
                    v=data.get('answer')
                    if v is not None and (type(v) is not int or v not in range(4)): raise ValueError('Javob noto‘g‘ri')
                    answers=json.loads(a['answers']);answers.append(v)
                    a.update(answers=json.dumps(answers),idx=a['idx']+1,deadline=now+30)
                    if a['idx']==15: a['finished']=now
                    c.execute('UPDATE attempts SET answers=?,idx=?,deadline=?,finished=? WHERE id=?',(a['answers'],a['idx'],a['deadline'],a['finished'],a['id']))
                return self.send(200,public_attempt(a))
        return self.send(404,{'error':'Topilmadi'})

def main():
    if os.environ.get('RENDER') and not DATABASE_URL:
        raise SystemExit('Render uchun DATABASE_URL ni Neon ulanish manziliga sozlang.')
    initialize()
    host=os.environ.get('HOST','0.0.0.0');port=int(os.environ.get('PORT','8000'))
    server=ThreadingHTTPServer((host,port),Handler);server.failures={}
    print(f'Test platforma: http://localhost:{port} | Admin: http://localhost:{port}/admin',flush=True)
    server.serve_forever()
if __name__=='__main__': main()
