
"""FastAPI server implementing the original CSV-based logic (main.py) but backed by SQLAlchemy.

Features replicated with DB storage:
    - User entries with calibration session workflow
    - Shaft & housing measurements (unique product_id enforcement)
    - Product existence checks
    - Measurement aggregation by roll number
    - Video listing & streaming with range requests (GET/HEAD)
    - Path debug endpoint
    - Data clearing endpoints returning original status strings

Differences:
    - Sessions stored in DB (UserSession table) instead of in-memory module.
    - CSV helper usage removed; timestamps stored as datetime.
    - Housing measurement retains optional height/depth columns.
"""

import os
import datetime
from typing import List, Optional
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from dotenv import load_dotenv
from sessions import (
    create_user_session,
    get_user_session,
    complete_user_session,
    cleanup_expired_sessions,
)
from sqlalchemy import inspect, text

# ----------------------------------------------------------------------------
# App & DB setup
# ----------------------------------------------------------------------------
load_dotenv()
DEBUG = os.getenv('API_DEBUG', '0') == '1'

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app_flask = Flask(__name__)
app_flask.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app_flask)


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class UserEntry(db.Model):
    __tablename__ = 'user_entry'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    last_login = db.Column(db.DateTime)


class MeasuredShaft(db.Model):
    __tablename__ = 'measured_shafts'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False, unique=True)
    roll_number = db.Column(db.String(50), nullable=False)
    shaft_height = db.Column(db.Float)
    shaft_radius = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)


class MeasuredHousing(db.Model):
    __tablename__ = 'measured_housings'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False, unique=True)
    roll_number = db.Column(db.String(50), nullable=False)
    housing_type = db.Column(db.String(50))
    housing_radius = db.Column(db.Float)
    # Optional extra columns (ignored by tests but allow capture if provided)
    housing_height = db.Column(db.Float)
    housing_depth = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)


with app_flask.app_context():  # Ensure tables exist (harmless if already created)
    try:
        db.create_all()
    except Exception:
        pass

    # Lightweight idempotent column additions (for dev environments without Alembic)
    # This inspects existing columns and issues ALTER TABLE only if needed.
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    try:
        shaft_cols = {c['name'] for c in inspector.get_columns('measured_shafts')}
        housing_cols = {c['name'] for c in inspector.get_columns('measured_housings')}
        if DEBUG:
            print('[DEBUG] measured_shafts existing columns:', shaft_cols)
            print('[DEBUG] measured_housings existing columns:', housing_cols)
        alter_stmts = []
        if 'shaft_height' not in shaft_cols:
            alter_stmts.append("ALTER TABLE measured_shafts ADD COLUMN shaft_height FLOAT")
        if 'shaft_radius' not in shaft_cols:
            alter_stmts.append("ALTER TABLE measured_shafts ADD COLUMN shaft_radius FLOAT")
        if 'housing_type' not in housing_cols:
            alter_stmts.append("ALTER TABLE measured_housings ADD COLUMN housing_type VARCHAR(50)")
        if 'housing_height' not in housing_cols:
            alter_stmts.append("ALTER TABLE measured_housings ADD COLUMN housing_height FLOAT")
        if 'housing_depth' not in housing_cols:
            alter_stmts.append("ALTER TABLE measured_housings ADD COLUMN housing_depth FLOAT")
        for stmt in alter_stmts:
            try:
                if DEBUG:
                    print('[DEBUG] Executing migration:', stmt)
                db.session.execute(text(stmt))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                if DEBUG:
                    print('[DEBUG] Migration failed/ignored:', stmt, 'error:', e)
    except Exception as e:
        if DEBUG:
            print('[DEBUG] Column inspection failed:', e)


# ----------------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(CURRENT_DIR, 'assets')
VIDEO_CATEGORY_DIRS = {
    'housing': 'housing',
    'shaft': 'shaft',
    'oval_housing': 'oval_housing',
    'sqaure_housing': 'sqaure_housing',  # keeping original misspelling
    'angular_housing': 'angular_housing'
}

def _list_category_files(category: str) -> List[str]:
    folder = VIDEO_CATEGORY_DIRS.get(category)
    if not folder:
        raise HTTPException(status_code=404, detail="Not Found")
    path = os.path.join(ASSETS_DIR, folder)
    if not os.path.isdir(path):
        return []
    return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

if DEBUG:
    @app.post("/_debug/db/shaft_insert")
    def debug_shaft_insert():
        """Attempt a dummy shaft insert to surface raw DB errors (debug mode only)."""
        import random
        pid = f"_DEBUG_SHAFT_{random.randint(1000,9999)}"
        with app_flask.app_context():
            try:
                obj = MeasuredShaft(product_id=pid, roll_number="_DEBUG", shaft_height=1.0, shaft_radius=2.0, timestamp=datetime.datetime.now())
                db.session.add(obj)
                db.session.commit()
                return {"status": "ok", "id": obj.id, "product_id": pid}
            except Exception as e:
                db.session.rollback()
                return {"status": "error", "error_type": type(e).__name__, "error": str(e)}


# ----------------------------------------------------------------------------
# Basic endpoints
# ----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Video API Server is running"}


@app.get("/housing_types")
def get_housing_types():
    return {"housing_types": ["oval", "sqaure", "angular"]}


@app.get("/debug/paths")
def debug_paths():
    return {
        "current_dir": CURRENT_DIR,
        "assets_dir": ASSETS_DIR,
        "video_dirs": {k: os.path.join(ASSETS_DIR, v) for k, v in VIDEO_CATEGORY_DIRS.items()},
        "dirs_exist": {k: os.path.isdir(os.path.join(ASSETS_DIR, v)) for k, v in VIDEO_CATEGORY_DIRS.items()}
    }


# ----------------------------------------------------------------------------
# Video endpoints
# ----------------------------------------------------------------------------
@app.get("/video/list/{category}")
def list_videos(category: str):
    files = _list_category_files(category)
    return JSONResponse(content=files)


@app.get("/video/housing_types/{housing_type}")
def list_housing_videos(housing_type: str):
    valid_types = ["oval", "sqaure", "angular"]
    if housing_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    category = f"{housing_type}_housing"
    files = _list_category_files(category)
    return JSONResponse(content=files)


def _validate_video_category(category: str):
    if category not in VIDEO_CATEGORY_DIRS:
        raise HTTPException(status_code=404, detail="Not Found")


CHUNK_SIZE = 1024 * 1024  # 1MB

def _get_video_path(category: str, filename: str) -> str:
    _validate_video_category(category)
    folder = VIDEO_CATEGORY_DIRS[category]
    file_path = os.path.join(ASSETS_DIR, folder, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return file_path

async def _range_streamer(file_path: str, start: int, end: int):
    with open(file_path, 'rb') as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)

@app.get("/video/{category}/{filename}")
@app.head("/video/{category}/{filename}")
async def stream_video(request: Request, category: str, filename: str):
    file_path = _get_video_path(category, filename)
    file_size = os.path.getsize(file_path)
    if request.method == 'HEAD':
        headers = {
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes'
        }
        return Response(headers=headers)
    range_header = request.headers.get('range')
    if range_header:
        try:
            range_value = range_header.strip().lower().split('bytes=')[1]
            start_str, end_str = range_value.split('-')
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            raise HTTPException(status_code=400, detail='Invalid Range header')
        if start > end or end >= file_size:
            raise HTTPException(status_code=416, detail='Requested Range Not Satisfiable')
        headers = {
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(end - start + 1),
            'Content-Type': 'video/mp4'
        }
        return StreamingResponse(_range_streamer(file_path, start, end), status_code=206, headers=headers)
    headers = {
        'Content-Length': str(file_size),
        'Content-Type': 'video/mp4',
        'Accept-Ranges': 'bytes'
    }
    return StreamingResponse(_range_streamer(file_path, 0, file_size - 1), headers=headers)


# ----------------------------------------------------------------------------
# Product existence
# ----------------------------------------------------------------------------
@app.get("/product_exists")
def product_exists_endpoint(product_id: str, measurement_type: str):
    if measurement_type not in ["shaft", "housing"]:
        raise HTTPException(status_code=400, detail="measurement_type must be 'shaft' or 'housing'")
    with app_flask.app_context():
        try:
            if measurement_type == "shaft":
                exists = MeasuredShaft.query.filter_by(product_id=product_id).first() is not None
            else:
                exists = MeasuredHousing.query.filter_by(product_id=product_id).first() is not None
        except Exception:
            db.session.rollback()
            exists = False
    return {"measurement_type": measurement_type, "product_id": product_id, "exists": exists}


# ----------------------------------------------------------------------------
# Measured units (aggregated by roll number)
# ----------------------------------------------------------------------------
@app.get("/measured_units/{roll_number}")
def get_measured_units_by_roll_number(roll_number: str):
    with app_flask.app_context():
        try:
            shaft_data = MeasuredShaft.query.filter_by(roll_number=roll_number).all()
            housing_data = MeasuredHousing.query.filter_by(roll_number=roll_number).all()
            shaft_filtered = [
                {
                    "id": s.id,
                    "product_id": s.product_id,
                    "shaft_height": s.shaft_height,
                    "shaft_radius": s.shaft_radius,
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None
                }
                for s in shaft_data
            ]
            housing_filtered = [
                {
                    "id": h.id,
                    "product_id": h.product_id,
                    "housing_type": h.housing_type,
                    "housing_height": h.housing_height,
                    "housing_radius": h.housing_radius,
                    "timestamp": h.timestamp.isoformat() if h.timestamp else None
                }
                for h in housing_data
            ]
        except Exception:
            db.session.rollback()
            shaft_filtered = []
            housing_filtered = []
    return {
        "status": "success",
        "roll_number": roll_number,
        "shaft_measurements": shaft_filtered,
        "housing_measurements": housing_filtered
    }


# ----------------------------------------------------------------------------
# Clear endpoints (status strings tailored to test expectations)
# ----------------------------------------------------------------------------
"""Schema management & generic query endpoints (replacing former CSV clear endpoints)."""

def _schema_inspector():
    return inspect(db.engine)

def _table_exists(table: str) -> bool:
    return table in _schema_inspector().get_table_names()

def _get_columns_meta(table: str):
    insp = _schema_inspector()
    return insp.get_columns(table)

def _get_pk_columns(table: str):
    insp = _schema_inspector()
    pk = insp.get_pk_constraint(table)
    cols = pk.get('constrained_columns') if pk else []
    return cols or []

@app.get("/db/schema/tables")
def list_tables_endpoint():
    try:
        with app_flask.app_context():
            insp = _schema_inspector()
            tables = sorted(insp.get_table_names())
            return {"tables": tables}
    except HTTPException:
        raise
    except Exception as e:
        if DEBUG:
            return JSONResponse(status_code=500, content={"detail": f"Schema list error: {type(e).__name__}: {e}"})
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/db/schema/tables/{table}")
def describe_table_endpoint(table: str):
    try:
        with app_flask.app_context():
            if not _table_exists(table):
                raise HTTPException(status_code=404, detail="Table not found")
            insp = _schema_inspector()
            cols = insp.get_columns(table)
            indexes = insp.get_indexes(table)
            pk = insp.get_pk_constraint(table)
            fks = insp.get_foreign_keys(table)
            return {
                "table": table,
                "columns": [
                    {
                        "name": c['name'],
                        "type": str(c['type']),
                        "nullable": c.get('nullable', True),
                        "default": c.get('default')
                    } for c in cols
                ],
                "primary_key": pk.get('constrained_columns') if pk else [],
                "indexes": indexes,
                "foreign_keys": fks
            }
    except HTTPException:
        raise
    except Exception as e:
        if DEBUG:
            return JSONResponse(status_code=500, content={"detail": f"Describe table error: {type(e).__name__}: {e}"})
        raise HTTPException(status_code=500, detail="Internal server error")

class SelectQueryBody(dict):
    pass

@app.post("/db/query/select")
def generic_select(body: dict = Body(...)):
    try:
        with app_flask.app_context():
            table = body.get("table")
            if not table:
                raise HTTPException(status_code=400, detail="Missing 'table'")
            if not _table_exists(table):
                raise HTTPException(status_code=404, detail="Table not found")
            columns_req = body.get("columns")  # list or None
            filters = body.get("filters", {}) or {}
            limit = body.get("limit", 100)
            offset = body.get("offset", 0)
            cols_meta = _get_columns_meta(table)
            valid_cols = {c['name'] for c in cols_meta}
            if columns_req:
                unknown = set(columns_req) - valid_cols
                if unknown:
                    raise HTTPException(status_code=400, detail=f"Unknown columns requested: {sorted(unknown)}")
            else:
                columns_req = sorted(valid_cols)
            where_clauses = []
            params = {}
            for i, (k, v) in enumerate(filters.items()):
                if k not in valid_cols:
                    raise HTTPException(status_code=400, detail=f"Unknown filter column: {k}")
                param_name = f"p{i}"
                where_clauses.append(f"{k} = :{param_name}")
                params[param_name] = v
            where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            col_sql = ", ".join(columns_req)
            sql = f"SELECT {col_sql} FROM {table}{where_sql} LIMIT :_limit OFFSET :_offset"
            params["_limit"] = limit
            params["_offset"] = offset
            with db.engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = [dict(r._mapping) for r in result]
            return {"table": table, "count": len(rows), "data": rows}
    except HTTPException:
        raise
    except Exception as e:
        if DEBUG:
            return JSONResponse(status_code=500, content={"detail": f"Select error: {type(e).__name__}: {e}"})
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/db/query/update")
def generic_update(body: dict = Body(...)):
    try:
        with app_flask.app_context():
            table = body.get("table")
            if not table:
                raise HTTPException(status_code=400, detail="Missing 'table'")
            if not _table_exists(table):
                raise HTTPException(status_code=404, detail="Table not found")
            set_values = body.get("set")
            if not set_values or not isinstance(set_values, dict):
                raise HTTPException(status_code=400, detail="Missing 'set' object with columns to update")
            filters = body.get("filters") or {}
            pk_values = body.get("pk")
            cols_meta = _get_columns_meta(table)
            valid_cols = {c['name'] for c in cols_meta}
            unknown_set = set(set_values.keys()) - valid_cols
            if unknown_set:
                raise HTTPException(status_code=400, detail=f"Unknown set columns: {sorted(unknown_set)}")
            pk_cols = _get_pk_columns(table)
            if pk_values is not None:
                if not pk_cols:
                    raise HTTPException(status_code=400, detail="Table has no primary key; use filters")
                if isinstance(pk_values, (list, tuple)):
                    if len(pk_cols) != 1:
                        raise HTTPException(status_code=400, detail="Composite PK updates via pk list not supported")
                    filters[pk_cols[0]] = pk_values[0]
                else:
                    filters[pk_cols[0]] = pk_values
            if not filters:
                raise HTTPException(status_code=400, detail="Refusing to update without filters or pk")
            set_parts = []
            params = {}
            for i, (k, v) in enumerate(set_values.items()):
                if k not in valid_cols:
                    raise HTTPException(status_code=400, detail=f"Unknown column in set: {k}")
                pname = f"s{i}"
                set_parts.append(f"{k} = :{pname}")
                params[pname] = v
            where_parts = []
            for j, (k, v) in enumerate(filters.items()):
                if k not in valid_cols:
                    raise HTTPException(status_code=400, detail=f"Unknown filter column: {k}")
                pname = f"f{j}"
                where_parts.append(f"{k} = :{pname}")
                params[pname] = v
            sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
            with db.engine.begin() as conn:
                res = conn.execute(text(sql), params)
                affected = res.rowcount
            return {"table": table, "updated": affected}
    except HTTPException:
        raise
    except Exception as e:
        if DEBUG:
            return JSONResponse(status_code=500, content={"detail": f"Update error: {type(e).__name__}: {e}"})
        raise HTTPException(status_code=500, detail="Internal server error")


# ----------------------------------------------------------------------------
# Shaft measurement CRUD
# ----------------------------------------------------------------------------
@app.get("/shaft_measurement")
def get_shaft_measurements():
    with app_flask.app_context():
        entries = MeasuredShaft.query.all()
        data = [
            {
                "id": e.id,
                "product_id": e.product_id,
                "roll_number": e.roll_number,
                "shaft_height": e.shaft_height,
                "shaft_radius": e.shaft_radius,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None
            }
            for e in entries
        ]
    return {"status": "success", "data": data}


@app.post("/shaft_measurement")
def add_shaft_measurement(entry: dict = Body(...)):
    required_fields = ["product_id", "roll_number", "shaft_height", "shaft_radius"]
    for field in required_fields:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    with app_flask.app_context():
        try:
            if MeasuredShaft.query.filter_by(product_id=entry["product_id"]).first():
                raise HTTPException(status_code=409, detail="product_id already exists for shaft measurements")
            new_entry = MeasuredShaft(
                product_id=entry["product_id"],
                roll_number=entry["roll_number"],
                shaft_height=entry["shaft_height"],
                shaft_radius=entry["shaft_radius"],
                timestamp=datetime.datetime.now()
            )
            db.session.add(new_entry)
            db.session.commit()
            return {"status": "shaft measurement added", "id": new_entry.id}
        except HTTPException:
            raise
        except Exception as e:
            db.session.rollback()
            detail = "Database error while adding shaft measurement"
            if DEBUG:
                detail += f": {type(e).__name__} - {e}"
            raise HTTPException(status_code=500, detail=detail)


@app.put("/shaft_measurement")
def update_shaft_measurement(entry: dict = Body(...)):
    if "product_id" not in entry:
        raise HTTPException(status_code=400, detail="Missing field: product_id")
    with app_flask.app_context():
        shaft = MeasuredShaft.query.filter_by(product_id=entry["product_id"]).first()
        if not shaft:
            raise HTTPException(status_code=404, detail="Entry not found")
        for field in ["roll_number", "shaft_height", "shaft_radius"]:
            if field in entry:
                setattr(shaft, field, entry[field])
        shaft.timestamp = datetime.datetime.now()
        db.session.commit()
    return {"status": "shaft measurement updated"}


@app.delete("/shaft_measurement")
def delete_shaft_measurements():
    with app_flask.app_context():
        MeasuredShaft.query.delete()
        db.session.commit()
    return {"status": "measured_shafts CSV deleted"}


# ----------------------------------------------------------------------------
# Housing measurement CRUD
# ----------------------------------------------------------------------------
@app.get("/housing_measurement")
def get_housing_measurements():
    with app_flask.app_context():
        entries = MeasuredHousing.query.all()
        data = [
            {
                "id": e.id,
                "product_id": e.product_id,
                "roll_number": e.roll_number,
                "housing_type": e.housing_type,
                "housing_radius": e.housing_radius,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None
            }
            for e in entries
        ]
    return {"status": "success", "data": data}


@app.post("/housing_measurement")
def add_housing_measurement(entry: dict = Body(...)):
    # Require both housing_height and housing_radius (align with original CSV logic)
    required_fields = ["product_id", "roll_number", "housing_type", "housing_height", "housing_radius"]
    for field in required_fields:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    valid_housing_types = ["housing", "oval", "sqaure", "angular"]
    if entry["housing_type"] not in valid_housing_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    with app_flask.app_context():
        try:
            if MeasuredHousing.query.filter_by(product_id=entry["product_id"]).first():
                raise HTTPException(status_code=409, detail="product_id already exists for housing measurements")
            new_entry = MeasuredHousing(
                product_id=entry["product_id"],
                roll_number=entry["roll_number"],
                housing_type=entry["housing_type"],
                housing_radius=entry["housing_radius"],
                housing_height=entry.get("housing_height"),
                housing_depth=entry.get("housing_depth"),
                timestamp=datetime.datetime.now()
            )
            db.session.add(new_entry)
            db.session.commit()
            return {"status": "housing measurement added", "id": new_entry.id}
        except HTTPException:
            raise
        except Exception as e:
            db.session.rollback()
            detail = "Database error while adding housing measurement"
            if DEBUG:
                detail += f": {type(e).__name__} - {e}"
            raise HTTPException(status_code=500, detail=detail)


@app.put("/housing_measurement")
def update_housing_measurement(entry: dict = Body(...)):
    if "product_id" not in entry:
        raise HTTPException(status_code=400, detail="Missing field: product_id")
    with app_flask.app_context():
        housing = MeasuredHousing.query.filter_by(product_id=entry["product_id"]).first()
        if not housing:
            raise HTTPException(status_code=404, detail="Entry not found")
        for field in ["roll_number", "housing_type", "housing_radius", "housing_height", "housing_depth"]:
            if field in entry:
                setattr(housing, field, entry[field])
        housing.timestamp = datetime.datetime.now()
        db.session.commit()
    return {"status": "housing measurement updated"}


@app.delete("/housing_measurement")
def delete_housing_measurements():
    with app_flask.app_context():
        MeasuredHousing.query.delete()
        db.session.commit()
    return {"status": "measured_housings CSV deleted"}


# ----------------------------------------------------------------------------
# User entry CRUD (optional)
# ----------------------------------------------------------------------------
def _should_calibrate(roll_number: str) -> bool:
    with app_flask.app_context():
        user = UserEntry.query.filter_by(roll_number=roll_number).first()
        if not user or not user.last_login:
            return True
        delta = datetime.datetime.now() - user.last_login
        return delta.total_seconds() > 24 * 3600


@app.get("/user_entry/should_calibrate")
def should_calibrate_endpoint(roll_number: str):
    return {"should_calibrate": _should_calibrate(roll_number)}


@app.get("/user_entry")
def get_user_entries():
    with app_flask.app_context():
        entries = UserEntry.query.all()
        if not entries:
            return {"status": "no records found", "data": []}
        data = [
            {
                "id": e.id,
                "roll_number": e.roll_number,
                "name": e.name,
                "date": e.date.isoformat() if e.date else None,
                "time": e.time.isoformat() if e.time else None,
                "last_login": e.last_login.isoformat() if e.last_login else None
            }
            for e in entries
        ]
    return {"status": "success", "data": data}


@app.post("/user_entry")
def add_user_entry(entry: dict = Body(...)):
    # Match main.py logic: only roll_number and name required
    cleanup_expired_sessions()
    for field in ["roll_number", "name"]:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    roll_number = entry["roll_number"].strip()
    name = entry["name"].strip()
    should_calibrate_flag = _should_calibrate(roll_number)
    with app_flask.app_context():
        existing = UserEntry.query.filter_by(roll_number=roll_number).first()
        user_status = "welcome_back" if existing else "new_user"
    session = create_user_session(roll_number=roll_number, name=name, should_calibrate=should_calibrate_flag)
    return {
        "session_id": session.session_id,
        "status": user_status,
        "should_calibrate": should_calibrate_flag,
        "message": "Session created. Complete calibration to finalize entry."
    }


@app.post("/user_entry/complete_calibration")
def complete_calibration(data: dict = Body(...)):
    if "session_id" not in data:
        raise HTTPException(status_code=400, detail="Missing session_id")
    session = get_user_session(data["session_id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.status == "calibrated":
        return {"status": "already_completed", "message": "Calibration already completed"}
    with app_flask.app_context():
        now = datetime.datetime.now()
        user = UserEntry.query.filter_by(roll_number=session.roll_number).first()
        if user:
            user.last_login = now
            user.date = now.date()
            user.time = now.time()
        else:
            user = UserEntry(
                roll_number=session.roll_number,
                name=session.name,
                date=now.date(),
                time=now.time(),
                last_login=now
            )
            db.session.add(user)
        db.session.commit()
    complete_user_session(session.session_id)
    return {
        "status": "calibration_completed",
        "roll_number": session.roll_number,
        "name": session.name,
        "message": "User entry finalized successfully"
    }


@app.get("/user_entry/session/{session_id}")
def get_session_status(session_id: str):
    session = get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session.to_dict()


@app.put("/user_entry")
def update_user_entry(entry: dict = Body(...)):
    if "roll_number" not in entry:
        raise HTTPException(status_code=400, detail="Missing field: roll_number")
    with app_flask.app_context():
        user = UserEntry.query.filter_by(roll_number=entry["roll_number"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="Entry with given roll_number not found")
        if "name" in entry:
            user.name = entry["name"]
        if "date" in entry:
            user.date = datetime.date.fromisoformat(entry["date"])
        if "time" in entry:
            user.time = datetime.time.fromisoformat(entry["time"])
        if "last_login" in entry:
            user.last_login = datetime.datetime.fromisoformat(entry["last_login"])
        db.session.commit()
    return {"status": "entry updated"}


@app.delete("/user_entry")
def delete_user_entries():
    with app_flask.app_context():
        UserEntry.query.delete()
        db.session.commit()
    return {"status": "user_entry CSV deleted"}


# ----------------------------------------------------------------------------
# Run (use uvicorn externally in production: uvicorn api:app --reload)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
