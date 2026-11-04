"""Connection contract checks. Does not require a hosted database."""
import sys, unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class DatabaseTests(unittest.TestCase):
 def test_bound_parameters_are_not_interpolated(self):
  raw=Mock();db=server.Database(raw,postgres=True)
  name="O'Connor ? 100%"
  db.execute('SELECT name FROM attempts WHERE name=?',(name,))
  raw.execute.assert_called_once_with('SELECT name FROM attempts WHERE name=%s',(name,))
 def test_commit_rollback_and_close(self):
  raw=Mock()
  with server.Database(raw):pass
  raw.commit.assert_called_once();raw.close.assert_called_once();raw.rollback.assert_not_called()
  raw=Mock()
  with self.assertRaises(ValueError):
   with server.Database(raw):raise ValueError('test')
  raw.rollback.assert_called_once();raw.close.assert_called_once();raw.commit.assert_not_called()
 def test_postgres_row_contract(self):
  cursor=Mock();cursor.description=[Mock(name='unused'),Mock(name='unused')]
  cursor.description[0].name='id';cursor.description[1].name='name'
  row=server.record_factory(cursor)(('123','Ali Valiyev'))
  self.assertEqual(row[0],'123');self.assertEqual(row['name'],'Ali Valiyev')
  self.assertEqual(dict(row),dict(id='123',name='Ali Valiyev'))
 def test_postgres_selection_fails_without_falling_back(self):
  driver=Mock();driver.connect.side_effect=RuntimeError('connection failed')
  with patch.object(server,'DATABASE_URL','postgresql://example/test'),patch.dict(sys.modules,{'psycopg':driver}),patch.object(server.sqlite3,'connect') as local:
   with self.assertRaises(RuntimeError):server.connect()
   local.assert_not_called()
if __name__=='__main__':unittest.main()
