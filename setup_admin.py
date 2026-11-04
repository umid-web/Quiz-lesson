"""Create an administrator interactively; existing credentials can be reset."""
import getpass, json, os, secrets
import server

def main():
    username=input('Admin login [admin]: ').strip() or 'admin'
    password=getpass.getpass('Yangi parol (kamida 10 belgi): ')
    if len(password)<10: raise SystemExit('Parol kamida 10 belgi bo‘lsin.')
    if password!=getpass.getpass('Parolni qayta yozing: '): raise SystemExit('Parollar mos emas.')
    os.environ['BOOTSTRAP_ADMIN_USERNAME']=username
    os.environ['BOOTSTRAP_ADMIN_PASSWORD']=password
    server.initialize()
    salt=secrets.token_hex(16)
    with server.connect() as c:
        c.execute("UPDATE config SET value=? WHERE key='admin'",(json.dumps(dict(username=username,salt=salt,hash=server.digest(password,salt))),))
        c.execute('DELETE FROM sessions')
    print('Admin tayyor. Endi: python server.py')
if __name__=='__main__': main()
