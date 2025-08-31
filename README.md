# Backend API Service Documentation

This backend service is built using FastAPI and provides APIs for video streaming, user entry management, and shaft measurement management. Data is stored in CSV files located in the `logs/` directory.

## Table of Contents

- [Setup](#setup)
- [API Endpoints](#api-endpoints)
  - [Root](#root)
  - [Debug Paths](#debug-paths)
  - [Video Streaming](#video-streaming)
  - [User Entry Management](#user-entry-management)
  - [Shaft Measurement Management](#shaft-measurement-management)
- [CSV Files](#csv-files)
- [Enhancements](#enhancements)

## Setup

- Requires Python 3.7+
- Install dependencies:
  ```
  pip install -r requirements.txt
  ```
- Run the server:
  ```
  uvicorn main:app --host 127.0.0.1 --port 8000
  ```

## API Endpoints

### Root

- `GET /`
- Returns a simple message indicating the server is running.

### Debug Paths

- `GET /debug/paths`
- Returns current directory, assets directory, video directories, and their existence status.

### Video Streaming

- `GET /video/list/{category}`
  - Lists video files in the specified category (`housing` or `shaft`).
- `GET /video/{category}/{filename}`
  - Streams the specified video file with support for HTTP range requests.

### User Entry Management

- `GET /user_entry`
  - Retrieves all user entries.
- `GET /user_entry/should_calibrate?roll_number={roll_number}`
  - Returns a flag `should_calibrate: bool` indicating if the user should calibrate.
  - If the user is new or last login was more than 24 hours ago, `should_calibrate` is `True`. Otherwise, `False`.
- `POST /user_entry`
  - Adds a new user entry or updates last login if roll number exists.
  - Request body fields: `roll_number`, `name`, optional `date`, `time`.
- `PUT /user_entry`
  - Updates an existing user entry by `roll_number`.
- `DELETE /user_entry`
  - Deletes the user entry CSV file.

### Shaft Measurement Management

- `GET /shaft_measurement`
  - Retrieves all shaft measurements.
- `POST /shaft_measurement`
  - Adds a new shaft measurement.
  - Request body fields: `part_number`, `roll_number`, `shaft_height`, `shaft_radius`.
- `PUT /shaft_measurement`
  - Updates an existing shaft measurement by `part_number`.
- `DELETE /shaft_measurement`
  - Deletes the shaft measurement CSV file.
- `DELETE /clear_measured_shafts`
  - Clears the shaft measurement CSV file.

## CSV Files

- `logs/user_entry.csv` - Stores user entry data.
- `logs/measured_shafts.csv` - Stores shaft measurement data.

CSV helper functions are implemented in `csv_helper.py` for reading, writing, and appending CSV files.

## Enhancements

- Consider adding Pydantic models for request validation.
- Implement authentication and authorization if needed.
- Add pagination and filtering for large datasets.
- Improve error handling and logging.
- Consider migrating from CSV files to a database for better concurrency and querying.
- Add unit and integration tests for API endpoints.
