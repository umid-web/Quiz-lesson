import http.cookiejar,json,os,tempfile,threading,time,unittest,urllib.error,urllib.request,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  server.DATABASE_URL=''
  cls.tmp=tempfile.TemporaryDirectory();server.DB=str(Path(cls.tmp.name)/'test.db')
  os.environ['BOOTSTRAP_ADMIN_PASSWORD']='Testing-only-98765';server.initialize()
  cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.http.failures={}
  threading.Thread(target=cls.http.serve_forever,daemon=True).start()
  cls.base=f'http://127.0.0.1:{cls.http.server_port}'
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,c,p,d=None,header=True):
  h={'Content-Type':'application/json'}
  if header:h['X-Quiz-Request']='1'
  r=urllib.request.Request(self.base+p,data=None if d is None else json.dumps(d).encode(),headers=h)
  try:
   with c.open(r) as v:return v.status,json.loads(v.read())
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
 def login(self,c):self.assertEqual(self.req(c,'/api/login',dict(username='admin',password='Testing-only-98765'))[0],200)
 def test_complete_and_central_results(self):
  c,a=self.client(),self.client();_,s=self.req(c,'/api/start',{'name':'Ali Valiyev'})
  self.assertNotIn('correct',s['question']);self.assertEqual(self.req(c,'/api/admin/results')[0],401)
  with server.LOCK, server.connect() as db:qs=json.loads(db.execute('SELECT questions FROM attempts WHERE id=?',(s['id'],)).fetchone()[0])
  for i,q in enumerate(qs):
   code,s=self.req(c,'/api/answer',dict(index=i,answer=q['correct']));self.assertEqual(code,200)
  self.assertTrue(s['finished']);self.assertEqual(s['score'],15);self.login(a)
  _,rows=self.req(a,'/api/admin/results');self.assertEqual(next(r for r in rows if r['id']==s['id'])['score'],15)
 def test_timeout_and_refresh(self):
  c=self.client();_,s=self.req(c,'/api/start',{'name':'Vali Aliyev'})
  self.assertEqual(self.req(c,'/api/state')[1]['deadline'],s['deadline'])
  with server.LOCK, server.connect() as db:db.execute('UPDATE attempts SET deadline=? WHERE id=?',(time.time()-31,s['id']))
  self.assertEqual(self.req(c,'/api/state')[1]['index'],2)
  code,r=self.req(c,'/api/answer',dict(index=0,answer=0));self.assertEqual(code,409);self.assertEqual(r['index'],2)
  with server.LOCK, server.connect() as db:db.execute('UPDATE attempts SET deadline=? WHERE id=?',(time.time()-500,s['id']))
  _,r=self.req(c,'/api/state');self.assertTrue(r['finished']);self.assertEqual(r['score'],0)
 def test_validation(self):
  c=self.client();self.assertEqual(self.req(c,'/api/start',{'name':'Ali Valiyev'},False)[0],403)
  self.assertEqual(self.req(c,'/api/start',{'name':'Ali'})[0],400)
  self.assertEqual(self.req(c,'/api/login',dict(username='admin',password='bad'))[0],401)
  self.login(c);self.assertEqual(self.req(c,'/api/admin/quiz',dict(title='X',questions=[]))[0],400)
 def test_snapshot_and_devices(self):
  a,b,c=self.client(),self.client(),self.client()
  _,s=self.req(a,'/api/start',{'name':'Bir xil'});_,t=self.req(b,'/api/start',{'name':'Bir xil'})
  self.assertNotEqual(s['id'],t['id']);self.login(c)
  _,q=self.req(c,'/api/admin/quiz');old=s['question']['text']
  for question in q['questions']:question['text']='Yangi: '+question['text']
  self.assertEqual(self.req(c,'/api/admin/quiz',q)[0],200)
  self.assertEqual(self.req(a,'/api/state')[1]['question']['text'],old)
  self.assertTrue(self.req(self.client(),'/api/start',{'name':'Yangi Odam'})[1]['question']['text'].startswith('Yangi: '))
  self.req(a,'/api/event',{});_,rows=self.req(c,'/api/admin/results')
  self.assertEqual(next(r for r in rows if r['id']==s['id'])['events'],1)
  self.req(c,'/api/admin/logout',{});self.assertEqual(self.req(c,'/api/admin/results')[0],401)
 def test_random_bank_and_stable_attempt(self):
  samples=[]
  for i in range(12):
   client=self.client();code,s=self.req(client,'/api/start',{'name':f'Test Odam{i}'})
   self.assertEqual(code,200)
   with server.LOCK, server.connect() as db:
    bank=json.loads(db.execute("SELECT value FROM config WHERE key='quiz'").fetchone()[0])['questions']
    picked=json.loads(db.execute('SELECT questions FROM attempts WHERE id=?',(s['id'],)).fetchone()[0])
   self.assertEqual(len(bank),50);self.assertEqual(len(picked),15)
   self.assertEqual(len({q['text'] for q in picked}),15)
   self.assertTrue(all(q in bank for q in picked))
   samples.append(tuple(q['text'] for q in picked))
   self.assertEqual(self.req(client,'/api/state')[1]['question'],s['question'])
   self.assertEqual(self.req(client,'/api/start',{'name':'Boshqa Ism'})[1]['id'],s['id'])
  self.assertGreater(len(set(samples)),1)
if __name__=='__main__':unittest.main()
