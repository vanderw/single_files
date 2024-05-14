import os
import requests
import subprocess
from datetime import datetime
from fabric import task, Connection


"""
Deploy scripts.
"""


class Server:
    '''
    '''
    def __init__(self, host, *, name='server', port=22, username='root', password='', pem='', 
                 user_group='www:www', temp_path='/tmp', deploy_path='/home', **kvargs) -> None:
        self.host = host
        self.name = name
        self.port = port
        self.username = username
        self.password = password
        self.pem = pem
        self.user_group = user_group
        self.temp_path = temp_path
        self.deploy_path = deploy_path
        self.kvargs = kvargs

    def backup_mysql(self, filepath)->bool:
        """
        Export mysql SQL, compress, download
        """
        params = {
            'key_filename': self.pem,
            'passphrase': '',
        } if self.pem else {
            'password': self.password,
        }

        sqlfile = f'{self.name}.sql'
        try:
            with Connection(host=self.host, port=self.port, user=self.username, connect_kwargs=params) as conn:
                with conn.cd(self.temp_path):
                    run(conn, f'mysqldump -h{self.kvargs['mysql_host']} -P{self.kvargs['mysql_port']} -u{self.kvargs['mysql_username']} -p{self.kvargs['mysql_password']} --databases {' '.join(self.kvargs['mysql_databases'])} > {sqlfile}')
                    run(conn, f"tar czf {sqlfile}.tar.gz {sqlfile}")
                    conn.get(os.path.join(self.temp_path, f'{sqlfile}.tar.gz'), local=os.path.join(os.path.dirname(filepath), datetime.now().strftime('%Y-%m-%d-%H.sql.tar.gz')))
                    run(conn, f"rm -f {sqlfile} {sqlfile}.tar.gz")
        except Exception as e:
            print('backup_mysql exception:', e)
            return False
        return True

    def upload(self, tarfile:str) -> bool:
        """
        Upload tarball to this server

        @tarfile: MUST locate in CURRENT directory
        @return bool
        """
        params = {
            'key_filename': self.pem,
            'passphrase': '',
        } if self.pem else {
            'password': self.password,
        }

        abs_remote_tar = os.path.join(self.temp_path, tarfile)
        try:
            with Connection(host=self.host, port=self.port, user=self.username, connect_kwargs=params) as conn:
                with conn.cd(self.temp_path):
                    conn.put(tarfile, remote=abs_remote_tar)
                    conn.run(f"tar xzf {abs_remote_tar} -C {self.deploy_path}")
                    conn.run(f"sudo chown -R {self.user_group} {self.deploy_path}")
                    conn.run(f"rm -f {abs_remote_tar}")
                    self.execute(conn)
        except Exception as e:
            print('upload exception:', e)
            return False
        return True

    def execute(self, conn):
        """
        Execute more commands
        """
        pass


class ServerGroup:
    def __init__(self, *, servers=[], domain='xyz.com', name='', tgmsg=False, chkbranch=False, **kvargs):
        self.servers = servers
        self.domain = domain
        self.name = name
        self.tgmsg = tgmsg
        self.chkbranch = chkbranch
        self.kvargs = kvargs


''''''
mapModeGroup = {
    'mysql': ServerGroup(servers=[
        Server(
            '192.168.1.1',
            name='mysql',
            password='123456',
            deploy_path='/home/test',
            mysql_host='192.168.1.2',
            mysql_port=3306,
            mysql_username='root',
            mysql_password='123456',
            mysql_databases=['db1', 'db2'],
        ),
    ]),
    'dev': ServerGroup(servers=[
        Server(
            '192.168.1.1', 
            name='dev',
            password='1234',
            deploy_path='/home/test',
        ),
    ]),
    'rel': ServerGroup(servers=[
        Server(
            '192.168.1.1',
            name='prod',
            password='1234',
            deploy_path='/home/test',
        ),
    ], chkbranch=True),
}
PATH_VERSION = './app/version'
TG_TOKEN = '',
TG_CHAT_ID = '',
TG_MSG = '新版本已发布'
TAR_FILENAME = 'upload.tar.gz'
TAR_ROOT = '/var/www/svideo_api'
TAR_INCLUDES = [
    'app', 'config'
]
TAR_EXCLUDES = [
    'config/platform.php'
]
''''''


def get_group(mode:str):
    return mapModeGroup.get(mode)


def check_mode(mode:str='prod', exit:bool=True):
    if mode not in mapModeGroup.keys():
        print(f"Please switch to {mode} branch")
        exit(-1)


def run(c, cmd):
    ''' Fabric Connection.run() wrapper'''
    return c.run(cmd, hide=True)


def git_branch()->str:
    """
    Get current git branch name
    """
    cmd = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    return subprocess.check_output(cmd).decode('ascii').strip()


def git_commit(short:bool=True)->str:
    '''
    Get git latest commit hash

    @short: is short hash or long(full)
    @return str
    '''
    cmd = ['git', 'rev-parse', '--short', 'HEAD']
    if not short:
        cmd = ['git', 'rev-parse', 'HEAD']
    return subprocess.check_output(cmd).decode('ascii').strip()


def git_last_log(n:int=3)->str:
    cmd = ['git', 'log', '--oneline', f"-{n}"]
    return subprocess.check_output(cmd).decode('utf8').strip()


def generate_version_file(filepath:str):
    """
    Generate a text file written current commit hash.

    @filepath: version file.
    """
    commit = git_commit()
    with open(filepath, 'wt', encoding='utf8') as fh:
        content = f"{commit}"
        fh.write(f"export const version='{content}'\n")


def compress_dir(c, filepath, dir='.', includes=[], excludes=[]):
    '''
    Compress a directory.

    @c: task context
    @filepath: .tar.gz file to be genrated
    @dir: target directory
    @includes: 1st level subdirectories included
    @excludes: files excluded.
    '''
    run(c, f"rm -f {filepath}")
    cmd = f"tar czf {filepath} -C {dir} {' '.join(['--exclude=' + item for item in excludes])} {' '.join(includes)}"
    run(c, cmd)


def compress_before(c):
    """
    Inject code before TAR_FILENAME generating.
    """
    print('in compress_before')


def compress_after(c):
    """
    Inject codes after TAR_FILENAME generated
    """
    print('in compress_after')


@task
def compress(c):
    """
    This is where defines HOW TAR_FILENAME generated
    """
    compress_before(c)
    compress_dir(c, TAR_FILENAME, TAR_ROOT, TAR_INCLUDES, TAR_EXCLUDES)
    compress_after(c)


@task
def upload(c, mode='dev'):
    """
    Upload TAR_FILENAME to servers defined in `mode`
    """
    if not os.path.isfile(TAR_FILENAME):
        print('File not found')
        return

    g = get_group(mode)

    success = [s for s in g.servers if s.upload(TAR_FILENAME)]

    if g.tgmsg:
        serverstr = ' '.join([f'{s.name}[*.*.*.{s.host.split(".")[3]}]' for s in success])
        tg_send(c, f'{TG_MSG} {serverstr}')


@task
def tg_send(c, msg='hello'):
    """
    Send an telegram message.
    """
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage?chat_id={TG_CHAT_ID}&text={msg}"
    ret = requests.get(url).json()
    if not ret['ok']:
        print('Send Telegram msg failed:', ret)


@task
def deploy(c, mode='dev'):
    check_mode(mode)

    g = get_group(mode)
    if g.chkbranch:
        branch = git_branch()
        if mode != branch:
            print(f'Branch is wrong, mode={mode} branch={branch}')
            exit(1)
    generate_version_file('./app/version')
    compress(c)
    upload(c, mode)
    print('Done.')


@task
def backupmysql(c, mode='mysql'):
    check_mode(mode)
    g = get_group(mode)

    _ = [s.backup_mysql('~/test.sql') for s in g.servers]


@task
def test(c):
    print('test')
    # backupmysql(c)
    # generate_version_file(PATH_VERSION)
    # compress(c)
    # upload(c, 'dev')
