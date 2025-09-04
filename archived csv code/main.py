import logging
from fastapi import FastAPI, Request, HTTPException, Response, Body
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from csv_helper import read_csv, write_csv, append_csv, csv_to_dict
import datetime
import csv
import time
from sessions import create_user_session, get_user_session, complete_user_session, cleanup_expired_sessions


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
current_dir= os.path.dirname(os.path.abspath(__file__))
print(f"Current directory: {current_dir}")

CSV_FILES = {
    "user_entry": {
        "path": os.path.abspath(os.path.join(current_dir, "logs", "user_entry.csv")),
        "fields": ["roll_number", "name", "date", "time"],
        "permission": "crud"
    }
}

print(f"CSV file path: {CSV_FILES['user_entry']}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the current directory and construct paths
current_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.abspath(os.path.join(current_dir, "assets"))

VIDEO_DIRS = {
    "housing": os.path.abspath(os.path.join(assets_dir, "housing")),
    "shaft": os.path.abspath(os.path.join(assets_dir, "shaft")),
    "oval_housing": os.path.abspath(os.path.join(assets_dir, "oval_housing")),
    "sqaure_housing": os.path.abspath(os.path.join(assets_dir, "sqaure_housing")),
    "angular_housing": os.path.abspath(os.path.join(assets_dir, "angular_housing")),
}

# Log the paths for debugging
logger.info(f"Current directory: {current_dir}")
logger.info(f"Assets directory: {assets_dir}")
for category, path in VIDEO_DIRS.items():
    logger.info(f"Video directory for {category}: {path}")
    logger.info(f"Directory exists: {os.path.exists(path)}")

CHUNK_SIZE = 1024 * 1024  # 1MB

@app.get("/")
async def root():
    return {"message": "Video API Server is running"}

@app.get("/measured_units/{roll_number}")
def get_measured_units_by_roll_number(roll_number: str):
    ensure_measured_shafts_csv_exists()
    ensure_measured_housings_csv_exists()
    shaft_data = read_csv(get_measured_shafts_path())
    housing_data = read_csv(get_measured_housings_path())
    shaft_filtered = [row for row in shaft_data if row.get("roll_number") == roll_number]
    housing_filtered = [row for row in housing_data if row.get("roll_number") == roll_number]
    return {
        "status": "success",
        "roll_number": roll_number,
        "shaft_measurements": shaft_filtered,
        "housing_measurements": housing_filtered
    }



@app.get("/debug/paths")
async def debug_paths():
    return {
        "current_dir": current_dir,
        "assets_dir": assets_dir,
        "video_dirs": VIDEO_DIRS,
        "dirs_exist": {k: os.path.exists(v) for k, v in VIDEO_DIRS.items()}
    }

def get_video_path(category: str, filename: str) -> str:
    logger.info(f"Getting video path for category: {category}, filename: {filename}")
    if category not in VIDEO_DIRS:
        logger.error(f"Category '{category}' not found in VIDEO_DIRS: {list(VIDEO_DIRS.keys())}")
        raise HTTPException(status_code=404, detail="Category not found")
    path = os.path.join(VIDEO_DIRS[category], filename)
    logger.info(f"Full video path: {path}")
    if not os.path.isfile(path):
        logger.error(f"File not found: {path}")
        raise HTTPException(status_code=404, detail="File not found")
    return path

async def range_streamer(file_path: str, start: int, end: int):
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            data = f.read(chunk_size)
            if not data:
                break
            yield data
            remaining -= len(data)

def get_video_list(category: str):
    """Helper function to get video list for a category"""
    logger.info(f"Listing videos for category: {category}")
    if category not in VIDEO_DIRS:
        logger.error(f"Category '{category}' not found. Available categories: {list(VIDEO_DIRS.keys())}")
        raise HTTPException(status_code=404, detail="Category not found")
    
    dir_path = VIDEO_DIRS[category]
    logger.info(f"Listing files in directory: {dir_path}")
    
    if not os.path.exists(dir_path):
        logger.error(f"Directory does not exist: {dir_path}")
        raise HTTPException(status_code=404, detail="Directory not found")
    
    try:
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        logger.info(f"Found {len(files)} files: {files}")
        return files
    except Exception as e:
        logger.error(f"Error listing directory {dir_path}: {e}")
        raise HTTPException(status_code=500, detail="Error listing directory")

@app.get("/video/list/{category}")
async def list_videos(category: str):
    files = get_video_list(category)
    return JSONResponse(content=files)

# List videos for specific housing type (must be BEFORE general video route)
@app.get("/video/housing_types/{housing_type}")
async def list_housing_videos(housing_type: str):
    valid_types = ["oval", "sqaure", "angular"]  # Match actual directory names
    if housing_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    
    category = f"{housing_type}_housing"  # This will create "oval_housing", "sqaure_housing", etc.
    files = get_video_list(category)
    return JSONResponse(content=files)

@app.get("/video/{category}/{filename}")
@app.head("/video/{category}/{filename}")
async def stream_video(request: Request, category: str, filename: str):
    file_path = get_video_path(category, filename)
    file_size = os.path.getsize(file_path)
    
    # For HEAD requests, just return headers without content
    if request.method == "HEAD":
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
        }
        return Response(headers=headers)
    
    range_header = request.headers.get("range")
    if range_header:
        # Example: Range: bytes=0-1023
        try:
            range_value = range_header.strip().lower().split("bytes=")[1]
            start_str, end_str = range_value.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Range header")
        if start > end or end >= file_size:
            raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(
            range_streamer(file_path, start, end),
            status_code=206,
            headers=headers,
        )
    else:
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
        }
        return StreamingResponse(
            range_streamer(file_path, 0, file_size - 1),
            headers=headers,
        )

from fastapi import HTTPException

def check_permission(file_key, action):
    perms = CSV_FILES[file_key]["permission"]
    if action == "create" and "c" not in perms:
        raise HTTPException(status_code=403, detail="Create not allowed")
    if action == "read" and "r" not in perms:
        raise HTTPException(status_code=403, detail="Read not allowed")
    if action == "update" and "u" not in perms:
        raise HTTPException(status_code=403, detail="Update not allowed")
    if action == "delete" and "d" not in perms:
        raise HTTPException(status_code=403, detail="Delete not allowed")

USER_ENTRY_FIELDS = ["roll_number", "name", "date", "time", "last_login"]

@app.get("/user_entry")
def get_user_entries():
    ensure_user_entry_csv_exists()
    data = read_csv(get_user_entry_path())
    if not data:
        return {"status": "no records found", "data": []}
    return {"status": "success", "data": data}
def should_calibrate_helper(roll_number: str) -> bool:
    """
    Checks if a user should calibrate based on last login.
    Returns True if user is new or last login > 24 hours ago.
    """
    ensure_user_entry_csv_exists()
    data = read_csv(get_user_entry_path())

    if not data:
        logging.info("No users in CSV — new user detected")
        return True

    now = datetime.datetime.now()
    for row in data:
        if row["roll_number"] == roll_number:
            last_login_str = row.get("last_login")
            if not last_login_str:
                logging.info("No last_login found — forcing calibration")
                return True
            try:
                last_login = datetime.datetime.fromisoformat(last_login_str)
            except Exception as e:
                logging.warning(f"Invalid last_login format '{last_login_str}' — {e}")
                return True
            delta = now - last_login
            logging.info(f"Time since last login for {roll_number}: {delta.total_seconds()} seconds")
            return delta.total_seconds() > 24 * 3600

    logging.info(f"User {roll_number} not found — new user detected")
    return True


@app.get("/user_entry/should_calibrate")
def should_calibrate_endpoint(roll_number: str):
    """Endpoint version — just calls the helper."""
    return {"should_calibrate": should_calibrate_helper(roll_number)}


@app.post("/user_entry")
def add_user_entry(entry: dict = Body(...)):
    """Create user session instead of immediate commit"""
    logging.info(f"Received entry: {entry}")
    cleanup_expired_sessions()  # Clean up old sessions
    
    for field in ["roll_number", "name"]:
        if field not in entry:
            logging.error(f"Missing field: {field}")
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")

    # Check if user exists and determine calibration requirement
    ensure_user_entry_csv_exists()
    should_calibrate_flag = should_calibrate_helper(entry["roll_number"])
    
    # Create session instead of immediate commit
    session = create_user_session(
        roll_number=entry["roll_number"], 
        name=entry["name"], 
        should_calibrate=should_calibrate_flag
    )
    
    logging.info(f"Created session {session.session_id} for user {entry['roll_number']}")
    
    # Check if returning user
    existing_entries = read_csv(get_user_entry_path())
    is_returning_user = any(row["roll_number"] == entry["roll_number"] for row in existing_entries)
    
    return {
        "session_id": session.session_id,
        "status": "welcome_back" if is_returning_user else "new_user",
        "should_calibrate": should_calibrate_flag,
        "message": "Session created. Complete calibration to finalize entry."
    }

@app.post("/user_entry/complete_calibration")
def complete_calibration(data: dict = Body(...)):
    """Complete calibration and commit user session to permanent records"""
    if "session_id" not in data:
        raise HTTPException(status_code=400, detail="Missing session_id")
    
    session = get_user_session(data["session_id"])
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if session.status == "calibrated":
        return {"status": "already_completed", "message": "Calibration already completed"}
    
    # Commit session to permanent records
    ensure_user_entry_csv_exists()
    existing_entries = read_csv(get_user_entry_path())
    
    # Check if user already exists
    user_exists = False
    for row in existing_entries:
        if row["roll_number"] == session.roll_number:
            # Update last_login for existing user
            row["last_login"] = datetime.datetime.now().isoformat()
            user_exists = True
            break
    
    if not user_exists:
        # Add new user
        now = datetime.datetime.now().isoformat()
        new_entry = {
            "roll_number": session.roll_number,
            "name": session.name,
            "date": now[:10],
            "time": now[11:19],
            "last_login": now
        }
        existing_entries.append(new_entry)
    
    # Save to file
    write_csv(get_user_entry_path(), existing_entries, USER_ENTRY_FIELDS)
    
    # Mark session as complete
    complete_user_session(data["session_id"])
    
    logging.info(f"Completed calibration for user {session.roll_number}")
    
    return {
        "status": "calibration_completed",
        "roll_number": session.roll_number,
        "name": session.name,
        "message": "User entry finalized successfully"
    }

@app.get("/user_entry/session/{session_id}")
def get_session_status(session_id: str):
    """Get session status"""
    session = get_user_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return session.to_dict()

@app.put("/user_entry")
def update_user_entry(entry: dict = Body(...)):
    """
    Update a user entry by roll_number. Expects a JSON body with roll_number and any fields to update.
    """
    ensure_user_entry_csv_exists()
    if "roll_number" not in entry:
        raise HTTPException(status_code=400, detail="Missing field: roll_number")

    entries = read_csv(get_user_entry_path())
    updated = False
    for row in entries:
        if row["roll_number"] == entry["roll_number"]:
            for field in USER_ENTRY_FIELDS:
                if field in entry and field != "roll_number":
                    row[field] = entry[field]
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Entry with given roll_number not found")

    write_csv(get_user_entry_path(), entries, USER_ENTRY_FIELDS)
    return {"status": "entry updated"}

@app.delete("/user_entry")
def delete_user_entries():
    path = get_user_entry_path()
    if os.path.exists(path):
        os.remove(path)
    return {"status": "user_entry CSV deleted"}

def get_user_entry_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "user_entry.csv")

def ensure_user_entry_csv_exists():
    path = get_user_entry_path()
    if not os.path.exists(path):
        from csv_helper import write_csv
        write_csv(path, [], ["roll_number", "name", "date", "time", "last_login"])

# Shaft measurement fields and CSV path
SHAFT_MEASUREMENT_FIELDS = ["product_id", "roll_number", "shaft_height", "shaft_radius", "timestamp"]
HOUSING_MEASUREMENT_FIELDS = ["product_id", "roll_number", "housing_type", "housing_height", "housing_radius", "timestamp"]


def get_measured_shafts_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "measured_shafts.csv")

def get_measured_housings_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return os.path.join(logs_dir, "measured_housings.csv")


def clear_user_entry_csv():
    path = get_user_entry_path()
    if os.path.exists(path):
        os.remove(path)
    return {"status": "user_entry CSV deleted"}



def clear_measured_shafts_csv():
    path = get_measured_shafts_path()
    if os.path.exists(path):
        os.remove(path)
    return {"status": "measured_shafts CSV deleted"}

def clear_measured_housings_csv():
    path = get_measured_housings_path()
    if os.path.exists(path):
        os.remove(path)
    return {"status": "measured_housings CSV deleted"}



def ensure_measured_shafts_csv_exists():
    path = get_measured_shafts_path()
    if not os.path.exists(path):
        from csv_helper import write_csv
        write_csv(path, [], SHAFT_MEASUREMENT_FIELDS)
    if os.path.getsize(path) == 0:
        from csv_helper import write_csv
        write_csv(path, [], SHAFT_MEASUREMENT_FIELDS)


def ensure_measured_housings_csv_exists():
    path = get_measured_housings_path()
    if not os.path.exists(path):
        from csv_helper import write_csv
        write_csv(path, [], HOUSING_MEASUREMENT_FIELDS)
    if os.path.getsize(path) == 0:
        from csv_helper import write_csv
        write_csv(path, [], HOUSING_MEASUREMENT_FIELDS)

# ---------------------------------------------------------------------------
# Product ID existence helpers & endpoint
# ---------------------------------------------------------------------------
def product_id_exists(product_id: str, measurement_type: str) -> bool:
    """Return True if a product_id already exists in the specified measurement CSV.

    measurement_type: 'shaft' or 'housing'
    """
    product_id = str(product_id).strip()
    if measurement_type == 'shaft':
        ensure_measured_shafts_csv_exists()
        rows = read_csv(get_measured_shafts_path())
    elif measurement_type == 'housing':
        ensure_measured_housings_csv_exists()
        rows = read_csv(get_measured_housings_path())
    else:
        raise HTTPException(status_code=400, detail="measurement_type must be 'shaft' or 'housing'")
    return any(str(r.get('product_id', '')).strip() == product_id for r in rows)

@app.get("/product_exists")
def product_exists_endpoint(product_id: str, measurement_type: str):
    """Check if a product_id exists for a given measurement type.

    Query Parameters:
      - product_id: ID to look for
      - measurement_type: 'shaft' or 'housing'
    Response: {"measurement_type": str, "product_id": str, "exists": bool}
    """
    exists = product_id_exists(product_id, measurement_type)
    return {
        "measurement_type": measurement_type,
        "product_id": product_id,
        "exists": exists
    }


# Shaft measurement endpoint
@app.post("/shaft_measurement")
def add_shaft_measurement(entry: dict = Body(...)):
    """
    Add a new shaft measurement. Expects a JSON body with product_id, roll_number, shaft_height, shaft_radius.
    Timestamp is automatically added.
    """
    ensure_measured_shafts_csv_exists()
    required_fields = ["product_id", "roll_number", "shaft_height", "shaft_radius"]
    
    for field in required_fields:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    # Enforce unique product_id per shaft dataset
    pid = str(entry.get('product_id')).strip()
    if product_id_exists(pid, 'shaft'):
        raise HTTPException(status_code=409, detail="product_id already exists for shaft measurements")
    
    # Add timestamp to entry
    entry["timestamp"] = datetime.datetime.now().isoformat()
    
    from csv_helper import append_csv
    append_csv(get_measured_shafts_path(), [entry], SHAFT_MEASUREMENT_FIELDS)
    
    return {
        "status": "shaft measurement added", 
        "product_id": pid,
        "timestamp": entry["timestamp"]
    }

# Housing measurement endpoint
@app.post("/housing_measurement")
def add_housing_measurement(entry: dict = Body(...)):
    """
    Add a new housing measurement. Expects a JSON body with product_id, roll_number, housing_type, housing_height, housing_radius.
    # housing_depth removed; only housing_height and housing_radius are used.
    Timestamp is automatically added.
    """
    ensure_measured_housings_csv_exists()
    
    # Required fields (housing_height and housing_radius)
    required_fields = ["product_id", "roll_number", "housing_type", "housing_height", "housing_radius"]
    for field in required_fields:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    # housing_depth logic removed
    
    # Validate housing_type value
    valid_housing_types = ["housing", "oval", "sqaure", "angular"]
    if entry["housing_type"] not in valid_housing_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    
    # Enforce unique product_id per housing dataset
    pid = str(entry.get('product_id')).strip()
    if product_id_exists(pid, 'housing'):
        raise HTTPException(status_code=409, detail="product_id already exists for housing measurements")
    
    # Add timestamp to entry
    entry["timestamp"] = datetime.datetime.now().isoformat()
    
    from csv_helper import append_csv
    append_csv(get_measured_housings_path(), [entry], HOUSING_MEASUREMENT_FIELDS)
    
    return {
        "status": "housing measurement added", 
        "product_id": pid,
        "timestamp": entry["timestamp"]
    }

@app.get("/shaft_measurement")
def get_shaft_measurements():
    ensure_measured_shafts_csv_exists()
    data = read_csv(get_measured_shafts_path())
    if not data:
        return {"status": "no records found", "data": []}
    return {"status": "success", "data": data}

@app.put("/shaft_measurement")
def update_shaft_measurement(entry: dict = Body(...)):
    """
    Update a shaft measurement by product_id. Expects a JSON body with product_id and any fields to update.
    Updates timestamp automatically when measurement is modified.
    """
    ensure_measured_shafts_csv_exists()
    if "product_id" not in entry:
        raise HTTPException(status_code=400, detail="Missing field: product_id")

    entries = read_csv(get_measured_shafts_path())
    updated = False
    for row in entries:
        if row["product_id"] == entry["product_id"]:
            # Update timestamp when measurement is modified
            entry["timestamp"] = datetime.datetime.now().isoformat()
            
            for field in SHAFT_MEASUREMENT_FIELDS:
                if field in entry and field != "product_id":
                    row[field] = entry[field]
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Entry with given product_id not found")

    write_csv(get_measured_shafts_path(), entries, SHAFT_MEASUREMENT_FIELDS)
    return {
        "status": "shaft measurement updated",
        "product_id": entry["product_id"],
        "timestamp": entry["timestamp"]
    }

@app.delete("/shaft_measurement")
def delete_shaft_measurements():
    path = get_measured_shafts_path()
    if os.path.exists(path):
        os.remove(path)
    return {"status": "measured_shafts CSV deleted"}

@app.delete("/clear_measured_shafts")
def clear_measured_shafts_endpoint():
    return clear_measured_shafts_csv()

# Get available housing types
@app.get("/housing_types")
def get_housing_types():
    return {
        "housing_types": [ "oval", "sqaure", "angular"],
    }

@app.post("/clear_shaft_csv")
async def clear_shaft_csv():
    """Clear all shaft measurement data"""
    try:
        shaft_path = get_measured_shafts_path()
        with open(shaft_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(SHAFT_MEASUREMENT_FIELDS)
        return {"status": "shaft CSV cleared", "timestamp": time.time()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing shaft CSV: {str(e)}")

@app.post("/clear_housing_csv")
async def clear_housing_csv():
    """Clear all housing measurement data"""
    try:
        housing_path = get_measured_housings_path()
        with open(housing_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(HOUSING_MEASUREMENT_FIELDS)
        return {"status": "housing CSV cleared", "timestamp": time.time()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing housing CSV: {str(e)}")

@app.post("/clear_user_entry_csv")
async def clear_user_entry_csv():
    """Clear all user entry data"""
    try:
        user_entry_path = get_user_entry_path()
        with open(user_entry_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(USER_ENTRY_FIELDS)
        return {"status": "user entry CSV cleared", "timestamp": time.time()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing user entry CSV: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)