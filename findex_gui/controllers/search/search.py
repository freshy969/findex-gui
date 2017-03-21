from flask_babel import gettext
from sqlalchemy_utils import escape_like
from sqlalchemy import func

from findex_gui import app, db
from findex_gui.orm.models import Files, Resource
from findex_common.static_variables import FileCategories, FileProtocols


class SearchResult:
    def __init__(self):
        self.results = []
        self.params = {}

    def to_json(self):
        blob = {
            'results': [z.to_json() for z in self.results],
            'params': self.params,
            'results_count': len(self.results)
        }

        return blob


class SearchController:
    def __init__(self):
        self._iface = self._get_iface()

    def _get_iface(self):
        #return DatabaseSearchController
        return ElasticSearchController

    def search(self, key, file_categories=[], file_extensions=[], file_size=[], file_type='both', page=0, per_page=30,
               autocomplete=False, lazy_search=False, **kwargs):

        result_obj = SearchResult()
        result_obj.results = self._iface.search(key=key,
                                                file_categories=file_categories,
                                                file_extensions=file_extensions,
                                                file_type=file_type,
                                                file_size=file_size,
                                                page=page,
                                                per_page=per_page,
                                                autocomplete=autocomplete,
                                                lazy_search=lazy_search)

        result_obj.params = {
            'key': key,
            'file_categories': file_categories,
            'file_extensions': file_extensions,
            'file_type': file_type,
            'file_size': file_size,
            'page': page,
            'per_page': per_page,
            'autocomplete': autocomplete
        }

        return result_obj


class ElasticSearchController:
    @staticmethod
    def search(**kwargs):
        # @TODO: filter by protocols / hosts
        # @TODO: replace by sqla - instead of a sqli-prone query builder
        kwargs["key"] = DatabaseSearchController.make_valid_key(kwargs['key'])

        _safe = lambda k: "".join(ch for ch in k if ch.isalnum())
        columns = [m.key for m in Files.__table__.columns]

        # start ZomboDB query
        sql = """SELECT %s FROM files WHERE zdb('files', files.ctid) ==>""" % ", ".join(columns)
        sql += """'(searchable:"*%s*")""" % kwargs["key"]

        if kwargs.get("file_categories"):
            _formats = [str(FileCategories().id_by_name(z)) for z in kwargs['file_categories']]
            if _formats:
                sql += " and file_format=(%s)" % ",".join(_formats)

        if kwargs.get("file_extensions"):
            _extensions = [_safe(z) for z in kwargs['file_extensions'] if _safe(z)]
            if _extensions:
                sql += " and file_ext=(%s)" % ",".join(_extensions)

        sql += "'"
        # end ZomboDB query

        if kwargs.get("autocomplete") and kwargs.get("autocomplete"):
            sql += " limit 5"

        sql += ";"

        try:
            results = db.session.execute(sql)
        except Exception as ex:
            print "ES search exception"
            return []

        data = []
        for res in results:
            z = Files()
            for c in columns:
                setattr(z, c, res[c])
            data.append(z)

        results = data
        resource_ids = set([z.resource_id for z in results])
        resource_obs = {z.id: z for z in Resource.query.filter(Resource.id.in_(resource_ids)).all()}

        for result in results:
            setattr(result, 'resource', resource_obs[result.resource_id])

        results = [result.fancify() for result in results]
        return results


class DatabaseSearchController:
    @staticmethod
    def search(**kwargs):
        kwargs['key'] = DatabaseSearchController.make_valid_key(kwargs['key'])

        # @TODO: filter by protocols / hosts
        q = Files.query

        # only find files that are not in 'temp' mode
        # q = q.filter(Files.resource_id >= 1)

        # ignores certain filters
        ignore_filters = []

        # filter only files/dirs, or both
        if 'folders' in kwargs['file_type'] and 'files' in kwargs['file_type']:
            pass
        elif 'folders' in kwargs['file_type']:
            q = q.filter(Files.file_isdir == True)

            # When searching only for directories, ignore filters that are not relevant
            ignore_filters.extend(('file_size', 'file_categories', 'file_extensions'))
        elif 'files' in kwargs['file_type']:
            q = q.filter(Files.file_isdir == False)

        # size
        if kwargs['file_size'] and 'file_size' not in ignore_filters:
            try:
                file_size = kwargs['file_size'].split('-')

                if not len(file_size) == 2:
                    raise Exception()

                if file_size[0] == '*':
                    q = q.filter(Files.file_size <= int(file_size[1]))
                elif file_size[1] == '*':
                    q = q.filter(Files.file_size >= int(file_size[0]))
                else:
                    q = q.filter(Files.file_size.between(*[int(x) for x in file_size]))
            except:
                pass

        # filter categories
        filecategories = FileCategories()

        cat_ids = []
        for cat in kwargs['file_categories']:
            cat_id = filecategories.id_by_name(cat)

            if cat_id is None:
                continue

            cat_ids.append(FileCategories().id_by_name(cat))

        if cat_ids and not 'file_categories' in ignore_filters:
            q = q.filter(Files.file_format.in_(cat_ids))

        if not kwargs['file_categories']:
            file_categories = filecategories.get_names()

        # filter extensions
        if kwargs['file_extensions'] and 'file_extensions' not in ignore_filters:
            exts = []

            for ext in kwargs['file_extensions']:
                if ext.startswith('.'):
                    ext = ext[1:]

                exts.append(ext)

            q = q.filter(Files.file_ext.in_(exts))

        # Search
        if kwargs['autocomplete'] or kwargs['lazy_search'] or app.config['db_file_count'] > 5000000:
            q = q.filter(Files.searchable.like(escape_like(kwargs['key']) + '%'))
        else:
            q = q.filter(Files.searchable.like('%' + escape_like(kwargs['key']) + '%'))

        # pagination
        q = q.offset(kwargs['page'])

        if kwargs['autocomplete']:
            q = q.limit(5)
            q = q.distinct(func.lower(Files.file_name))
        else:
            q = q.limit(kwargs['per_page'])

        # fetch
        results = q.all()

        resource_ids = set([z.resource_id for z in results])
        resource_obs = {z.id: z for z in Resource.query.filter(Resource.id.in_(resource_ids)).all()}

        for result in results:
            setattr(result, 'resource', resource_obs[result.resource_id])

        results = [result.fancify() for result in results]
        return results

    @staticmethod
    def make_valid_key(key):
        # `Files.searchable` does not have any of these characters, strip them.
        for clean in ['-', ',', '+', '_', '%']:
            key = key.replace(clean, ' ')

        if len(key) <= 1:
            raise Exception(gettext('Search key too short'))

        return key.lower()
