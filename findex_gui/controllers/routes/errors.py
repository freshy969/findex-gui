import settings
from findex_gui import app


@app.errorhandler(404)
def page_not_found(e):
    print e
    return '404', 404


@app.errorhandler(Exception)
def all_exception_handler(error):
    rtn = 'Error'

    if settings.app_debug:
        rtn += ': %s' % str(error)

    return rtn, 500