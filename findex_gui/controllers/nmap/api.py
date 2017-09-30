from flask import jsonify
from flask_yoloapi import endpoint, parameter

from findex_gui.web import app, db
from findex_gui.orm.models import NmapRule
from findex_gui.controllers.user.decorators import admin_required
from findex_gui.controllers.nmap.nmap import NmapController

@app.route("/api/v2/admin/server/nmap/add", methods=["POST"])
@admin_required
@endpoint.api(
    parameter("rule", type=str, required=True),
    parameter("name", type=str, required=True)
)
def api_admin_server_nmap_add(rule, name):
    return NmapController.add(cmd=rule, name=name)

@app.route("/api/v2/admin/server/nmap/delete", methods=["POST"])
@admin_required
@endpoint.api(
    parameter("uid", type=int, required=True)
)
def api_admin_server_nmap_remove(uid):
    return NmapController.remove(uid)

@app.route("/api/v2/admin/server/nmap/get", methods=["GET"])
@endpoint.api(
    parameter("uid", type=str, required=False),
    parameter("perPage", type=int, required=False, default=None),
    parameter("page", type=int, required=False, default=None)
)
def api_admin_server_nmap_get(uid, perPage, page):
    """
    Get resources.
    :param uid: nmap uid
    :param perPage:
    :param page:
    :return: nmap_rule object
    """
    args = {}
    if perPage:
        args["limit"] = perPage
        if page:
            args["offset"] = (page - 1) * perPage

    resources = NmapController.get(**args)

    from sqlalchemy import func

    # total_count = select([func.count()]).select_from(NmapRule)
    # records_total = db.session.execute(total_count)

    e = db.session.query(func.count(NmapRule.id)).scalar()
    e = ""
    return jsonify({
        "records": resources,
        "queryRecordCount": e,
        "totalRecordCount": len(resources)
    })