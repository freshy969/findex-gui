from urllib import quote_plus, unquote_plus
from datetime import datetime

from findex_gui.db.orm import Files, Hosts
from findex_gui.controllers.findex.findex import Findex

from findex_common.bytes2human import bytes2human
from findex_common.exceptions import BrowseException


class Browser():
    def __init__(self, db):
        self.db = db
        self.findex = Findex(db)

        self.env = {}
        self.data = {}
        self.files = None

    def parse_incoming_path(self, path):
        self.data['isdir'] = path.endswith('/')

        spl = path.split('/')
        self.data['host'] = spl[0]
        self.data['file_path'] = '/' + '/'.join(spl[1:-1])

        if not self.data['isdir']: self.data['file_name'] = path.split('/')[-1]
        if self.data['file_path'] != '/': self.data['file_path'] += '/'

        self.data['file_path_quoted'] = quote_plus(self.data['file_path'])

    def fetch_files(self):
        host = self.db.query(Hosts).filter_by(
            address=self.data['host']
        ).first()

        if not host:
            raise BrowseException('No host found')

        self.data['host_id'] = host.id
        files = self.findex.get_files_objects(host_id=host.id, file_path=self.data['file_path_quoted'])

        if not files:
            raise BrowseException('No files found')

        self.files = files

    def prepare_files(self, env, sort=None):
        self.env = env

        # sort files
        self.files = sorted(self.files, key=lambda k: k.file_name)  # alphabetically
        self.files = sorted(self.files, key=lambda k: k.file_isdir, reverse=True)  # folders always on top

        if not self.data['file_path'] == '/':  # add CDUP dirs
            x = Files(
                file_name='..', file_path='../', file_ext='', file_format=-1,
                file_isdir=True, file_modified=datetime.now(), file_perm=None, searchable=None,
                file_size=0, host=self.data['host']
            )
            setattr(x, 'file_name_human', '..')
            self.files.insert(0, x)

        self.files = self.findex.set_icons(env=env, files=self.files)

    def sort(self):
        # calculate total folder file size (non-recursive)
        total_size = 0
        for f in self.files:
            total_size += f.file_size

    def generate_action_fetches(self):
        url = 'ftp://%s' % self.data['host']

        if self.data['file_path'] == '/':
            path = ''
        elif self.data['file_path'].startswith('/') and url.endswith('/'):
            path = self.data['file_path'][1:]

        wget_extras = ''
        lftp_extras = ''

        # if self.source.crawl_authtype:
        #     wget_extras = 'user=%s password=%s ' % (self.source.crawl_username, self.source.crawl_password)
        #
        #     if self.source.crawl_authtype == 'HTTP_DIGEST':
        #         lftp_extras = Debug('Authentication using DIGEST is not supported by lftp')
        #     else:
        #         lftp_extras = '-u %s,%s ' % (self.source.crawl_username, self.source.crawl_password)

        wget = 'wget %s-r -nH --no-parent \'%s\'' % (wget_extras, url + self.data['file_path'])

        #if not isinstance(lftp_extras, Debug):
        lftp = 'lftp %s-e \'mirror\' \'%s\'' % (lftp_extras, url + self.data['file_path'])
        #else:
        #    lftp = lftp_extras.message

        return dict(wget=wget, lftp=lftp)

    def breadcrumbs(self):
        data = [self.data['host']]
        data += [z for z in self.data['file_path'].split('/')[1:] if z]

        return data

    def output_json(self):
        data = []

        for source_file in self.files:
            if source_file.filename_human == '..':
                continue

            data.append('[%s] %s%s%s' % (
                'D' if source_file.is_directory else 'F',
                self.folder.source.crawl_url,
                source_file.filepath_human,
                source_file.filename_human))

        return '\n'.join(data)