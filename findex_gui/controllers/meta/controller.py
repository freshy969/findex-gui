import os
import json
from typing import List

from findex_gui.web import db
from findex_gui.orm.models import MetaMovies, MetaMovies, Files
from findex_gui.controllers.user.decorators import admin_required

from findex_common.exceptions import SearchException
from sqlalchemy_utils import escape_like
from sqlalchemy_zdb import ZdbQuery
from sqlalchemy_zdb.types import ZdbLiteral


class MetaController:
    @staticmethod
    @admin_required
    def load_new_db(path_metadata_zip):
        basename = os.path.basename(path_metadata_zip)
        dirname = os.path.basename(path_metadata_zip)
        os.popen("cd %s && unzip %s" % (dirname, basename)).read()

        f = open("%s/info.txt")
        info = json.loads(f.read())
        f.close()

        if os.path.isfile("%s/meta_movies.txt" % basename):
            db.session.query(MetaMovies).delete(synchronize_session=False)
            db.session.commit()
            db.session.flush()

            f = open("%s/meta_movies.txt" % basename, "r")
            movies = f.readlines()
            f.close()

            movies = [json.loads(movie) for movie in movies]

            objects = []
            for movie in movies:
                m = MetaMovies(
                    title=movie["title"],
                    year=movie["year"],
                    rating=movie["year"],
                    plot=movie["plot"],
                    director=movie["director"],
                    genres=movie["genres"],
                    actors=movie["actors"],
                    meta=movie.get("meta", {})
                )
                objects.append(m)
            db.session.bulk_save_objects(objects)
            db.session.commit()
            db.session.flush()


class MetaPopcornController:
    @staticmethod
    def get(imdb_id):
        return db.session.query(MetaMovies).filter(MetaMovies.id == imdb_id).first()

    @staticmethod
    def get_director(search=None):
        q = ZdbQuery(MetaMovies, session=db.session)
        if search:
            search = search.lower()
            search = search.replace("*", "")
            if not isinstance(search, str):
                raise SearchException("search must be str")
            q = q.filter(MetaMovies.director == ZdbLiteral("\"%s*\"" % search))
            # q = q.filter(MetaMovies.director.distinct()) distinct not implmeneted yet in ZdbQuery
        results = [z.director for z in q.all()]
        return list(set(results))

    @staticmethod
    def get_actors(search=None):
        if len(search) < 3:
            return []

        q = ZdbQuery(MetaMovies, session=db.session)
        if search:
            search = search.lower()
            search = search.replace("*", "")
            if not isinstance(search, str):
                raise SearchException("search must be str")
            q = q.filter(MetaMovies.actors == ZdbLiteral("\"%s*\"" % search))
        results = q.all()

        actors = []
        for result in results:
            for actor in result.actors:
                if search not in actor.lower():
                    continue
                if actor not in actors:
                    actors.append(actor)
        return actors

    @staticmethod
    def get_actor_played_in(actor):
        """Returns a list of movies given an actor/actress"""

        q = ZdbQuery(MetaMovies, session=db.session)
        q = q.filter(MetaMovies.actors.like(actor))
        results_imdb = q.all()
        if not results_imdb:
            return {
                "local": [],
                "imdb": []
            }

        ids = [z.id for z in results_imdb]
        results_imdb = sorted(results_imdb, key=lambda x: x.rating, reverse=True)

        q = ZdbQuery(Files, session=db.session)
        q = q.filter(Files.meta_movie_id.in_(ids))
        q = q.filter(Files.file_size >= 134217728)
        results_local = q.all()
        # @TODO: migrate `meta_info` to JSONB so we get the #> operator
        # with that we can DISTINCT on nested json key 'title'
        # e.g: SELECT DISTINCT ON (files.meta_info#>'{ptn, title}')
        # to prevent from returning duplicates in popcorn view.
        # for now, lets just do this:
        _names = []
        _rtn = []
        for result in results_local:
            result.get_meta_movie()
            if result.meta_movie.title not in _names:
                _rtn.append(result)
                _names.append(result.meta_movie.title)
        _rtn = sorted(_rtn, key=lambda x: x.meta_movie.title, reverse=True)

        return {
            "local": _rtn,
            "imdb": results_imdb
        }

    @staticmethod
    def get_director_directed(director):
        """Returns a list of movies given a director"""

        q = ZdbQuery(MetaMovies, session=db.session)
        q = q.filter(MetaMovies.director.like(director))
        results_imdb = q.all()
        if not results_imdb:
            return {
                "local": [],
                "imdb": []
            }

        ids = [z.id for z in results_imdb]
        results_imdb = sorted(results_imdb, key=lambda x: x.rating, reverse=True)

        q = ZdbQuery(Files, session=db.session)
        q = q.filter(Files.meta_movie_id.in_(ids))
        q = q.filter(Files.file_size >= 134217728)

        results_local = q.all()
        # @TODO: migrate `meta_info` to JSONB so we get the #> operator
        # with that we can DISTINCT on nested json key 'title'
        # e.g: SELECT DISTINCT ON (files.meta_info#>'{ptn, title}')
        # to prevent from returning duplicates in popcorn view.
        # for now, lets just do this:
        _names = []
        _rtn = []
        for result in results_local:
            result.get_meta_movie()
            if result.meta_movie.title not in _names:
                _rtn.append(result)
                _names.append(result.meta_movie.title)
        _rtn = sorted(_rtn, key=lambda x: x.meta_movie.title, reverse=True)
        return {
            "local": _rtn,
            "imdb": results_imdb
        }

    @staticmethod
    def search(actors: List = None, genres: List = None, min_rating: int = None,
               director: str = None, year: int = None,
               offset: int = None, limit: int = 12, title=None):
        if actors and not isinstance(actors, list):
            raise SearchException("actors must be list")
        if genres and not isinstance(genres, list):
            raise SearchException("genres must be list")
        if min_rating:
            if not isinstance(min_rating, (int, float)):
                raise SearchException("min_rating must be int")
            if not min_rating > 0 or min_rating > 100:
                raise SearchException("min_rating must be between 1-100")
            if min_rating <= 10:
                min_rating = int(min_rating * 10)
        if director and not isinstance(director, str):
            raise SearchException("director must be str")
        if title and not isinstance(title, str):
            raise SearchException("title must be str and not empty")
        if title and len(title) < 3:
            title = None
        if year and not isinstance(year, int):
            raise Exception("year must be int")
        if offset and not isinstance(offset, int):
            raise Exception("offset must be int")
        if limit and not isinstance(limit, int):
            raise Exception("limit must be int")

        if actors or genres or min_rating or director or year or title:
            q = ZdbQuery(MetaMovies, session=db.session)
        else:
            q = ZdbQuery(Files, session=db.session)
            q = q.filter(Files.meta_movie_id != None)
            q = q.filter(Files.file_size >= 134217728)
            q = q.distinct(Files.meta_movie_id)
            q = q.limit(100)

            if offset:
                q = q.offset(offset)

            results = q.all()

            # for every result, fetch meta
            q = db.session.query(MetaMovies)
            metas = q.filter(MetaMovies.id.in_([z.meta_movie_id for z in results])).all()
            metas = {z.id: z for z in metas}

            # assign metas
            for result in results:
                if result.meta_movie_id in metas:
                    result.meta_movie = metas[result.meta_movie_id]
            return results

        if actors:
            q = q.filter(MetaMovies.actors.in_(actors))

        if genres:
            for i in genres:
                q = q.filter(MetaMovies.genres == i)

        if min_rating:
            q = q.filter(MetaMovies.rating >= min_rating)

        if year:
            q = q.filter(MetaMovies.year == year)

        if director:
            q = q.filter(MetaMovies.director == director)

        if title:
            q = q.filter(MetaMovies.title == ZdbLiteral("\"%s*\"" % title))
            # q = q.filter(MetaMovies.title.like(escape_like(title)))

        results = q.all()
        if not results:
            return []

        ids = list(set([z.id for z in results]))

        q = ZdbQuery(Files, session=db.session)
        q = q.filter(Files.file_format == 2)
        q = q.filter(Files.file_size >= 134217728)
        q = q.filter(Files.meta_movie_id.in_(ids))
        q = q.limit(100)
        results = q.all()

        _names = []
        _rtn = []
        for result in results:
            result.get_meta_movie()
            if result.meta_movie.title not in _names:
                _rtn.append(result)
                _names.append(result.meta_movie.title)
        return _rtn

# @TODO: migrate `meta_info` to JSONB so we get the #> operator
# with that we can DISTINCT on nested json key 'title'
# e.g: SELECT DISTINCT ON (files.meta_info#>'{ptn, title}')
# to prevent from returning duplicates in popcorn view.
# for now, lets just do this: