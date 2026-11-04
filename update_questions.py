"""Replace the question bank while keeping existing results and admin credentials."""
import json
from pathlib import Path
import server

def main():
 if not Path(server.DB).exists():
  raise SystemExit('Avval python setup_admin.py orqali bazani yarating.')
 server.initialize()
 q=server.validate_quiz(json.loads((server.ROOT/'questions.example.json').read_text(encoding='utf-8')))
 with server.connect() as c:
  c.execute("UPDATE config SET value=? WHERE key='quiz'",(json.dumps(q,ensure_ascii=False),))
 print('50 savollik yangi bank yuklandi. Eski natijalar va faol urinishlar saqlandi.')
if __name__=='__main__':main()
