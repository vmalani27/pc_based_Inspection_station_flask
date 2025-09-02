# PC-Based Inspection Station - Backend API

A FastAPI-based backend service for managing PC-based inspection station operations, including user management, device calibration, measurement recording, and video streaming.

## Live Production
- **URL**: https://pcbis.flashstudios.tech
- **Hosted on**: Heroku with PostgreSQL database
- **SSL**: Automatically managed with Let's Encrypt

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [API Endpoints](#api-endpoints)
- [Session Management](#session-management)
- [Database Schema](#database-schema)
- [Deployment](#deployment)
- [Development](#development)
- [Frontend Integration](#frontend-integration)

## Features

### Session-Based User Management
- Temporary session creation on login
- Calibration-dependent user entry finalization
- Prevents incomplete data records
- Auto-session cleanup (1-hour expiry)

### Measurement Tracking
- Shaft measurements (height, radius) with timestamps
- Housing measurements (depth, height, radius) with timestamps
- Multiple housing types: standard, oval, square, angular
- Unique product ID enforcement
- Automatic timestamp generation

### Video Streaming
- HTTP range request support
- Multiple video categories
- Adaptive streaming for different housing types

### Dual Storage System
- **Production**: PostgreSQL database with automatic backups
- **Development**: CSV files for local testing
- **Timestamps**: Automatic measurement and creation timestamps

## Architecture

```
Frontend (Flutter) ←→ FastAPI Backend ←→ PostgreSQL/CSV
                             ↓
                     Session Management
                             ↓
                      Video Streaming
```

### **Branch Structure**
- `main` - Production branch (auto-deployed to Heroku)
- `database-integration` - Development branch
- `feature/*` - Feature development branches

## Setup

### Requirements
- Python 3.9+
- PostgreSQL (production) or SQLite (development)

### Installation
```bash
# Clone repository
git clone https://github.com/vmalani27/pc_based_Inspection_station_flask.git
cd pc_based_Inspection_station_flask

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

**Local server**: http://127.0.0.1:5000

## API Endpoints

### Root & Health
- `GET /` - Health check
- `GET /debug/paths` - Debug information

### Session Management
- `POST /user_entry` - Create user session
- `POST /user_entry/complete_calibration` - Complete calibration & finalize entry
- `GET /user_entry/session/{session_id}` - Get session status
- `GET /user_entry/should_calibrate` - Check calibration requirement

### Measurements
- `POST /shaft_measurement` - Record shaft measurement
- `GET /shaft_measurement` - Get all shaft measurements
- `PUT /shaft_measurement` - Update shaft measurement
- `POST /housing_measurement` - Record housing measurement  
- `GET /housing_measurement` - Get all housing measurements

### Video Streaming
- `GET /video/list/{category}` - List videos in category
- `GET /video/{category}/{filename}` - Stream video file

### Utilities
- `GET /housing_types` - Get available housing types
- `GET /product_exists` - Check if product ID exists
- `DELETE /clear_*` - Clear measurement data

## Session Management

### Workflow
1. **User Login** → Creates temporary session
2. **Calibration Check** → Determines if calibration required
3. **Device Calibration** → User performs calibration
4. **Session Completion** → Permanent record created
5. **Auto Cleanup** → Expired sessions removed

### Session States
- `pending_calibration` - Awaiting calibration completion
- `calibrated` - Session completed successfully
- `expired` - Session timed out (1 hour)

```json
{
  "session_id": "abc123-def456-...",
  "status": "new_user",
  "should_calibrate": true,
  "message": "Session created. Complete calibration to finalize entry."
}
```

## Database Schema

### UserEntry
```sql
CREATE TABLE user_entries (
    id SERIAL PRIMARY KEY,
    roll_number VARCHAR,
    name VARCHAR,
    date VARCHAR,
    time VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### ShaftMeasurement
```sql
CREATE TABLE shaft_measurements (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR UNIQUE,
    roll_number VARCHAR,
    shaft_height FLOAT,
    shaft_radius FLOAT,
    measurement_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### HousingMeasurement
```sql
CREATE TABLE housing_measurements (
    id SERIAL PRIMARY KEY,
    product_id VARCHAR UNIQUE,
    roll_number VARCHAR,
    housing_type VARCHAR,
    depth FLOAT,
    radius FLOAT,
    height FLOAT,
    measurement_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Deployment

### Production (Heroku)
```bash
# Add PostgreSQL
heroku addons:create heroku-postgresql:essential-0

# Configure custom domain
heroku domains:add pcbis.flashstudios.tech

# Enable SSL
heroku certs:auto:enable

# Deploy
git push heroku main
```

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string (auto-set by Heroku)
- `PORT` - Application port (auto-set by Heroku)

## Development

### Local Development
```bash
# Start with hot reload
uvicorn main:app --reload --host 127.0.0.1 --port 5000

# Or direct Python
python main.py
```

### Testing
```bash
# Load testing
python load_test.py

# Enter URL: https://pcbis.flashstudios.tech
```

### Branch Workflow
```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes, test locally
python main.py

# Commit to feature branch (safe)
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# Merge to production when ready
git checkout main
git merge feature/new-feature
git push heroku main
```

## Frontend Integration

### Flutter Implementation
Complete Flutter integration guide available in `Flutter_Implementation_Guide.md`

### Key Integration Points
```dart
// 1. Create session on login
final loginResponse = await createUserSession(rollNumber, name);
sessionStorage.setItem('user_session_id', loginResponse.sessionId);

// 2. Complete calibration
final success = await completeCalibration();

// 3. Record measurements with timestamps
final measurement = await recordShaftMeasurement({
  'product_id': 'PROD_001',
  'roll_number': 'ROLL_123',
  'shaft_height': 25.4,
  'shaft_radius': 12.7
  // timestamp added automatically
});
```

## Recent Updates

### v2.0 - Database Integration
- PostgreSQL database integration
- Session-based user management
- Automatic timestamps on all measurements
- Enhanced error handling
- Production deployment on Heroku

### v1.0 - MVP
- CSV-based storage
- Basic user entry
- Measurement recording
- Video streaming

## Configuration

### Housing Types
- `housing` - Standard circular housing
- `oval` - Oval/elliptical housing
- `sqaure` - Square housing (note: typo preserved for compatibility)
- `angular` - Angular/polygonal housing

### File Structure
```
├── main.py              # FastAPI application
├── database.py          # Database models and connection
├── sessions.py          # Session management
├── csv_helper.py        # CSV utilities
├── requirements.txt     # Python dependencies
├── Procfile            # Heroku deployment config
├── logs/               # CSV storage (local development)
│   ├── user_entry.csv
│   ├── measured_shafts.csv
│   └── measured_housings.csv
└── assets/             # Video files
    ├── housing/
    ├── shaft/
    ├── oval_housing/
    ├── sqaure_housing/
    └── angular_housing/
```

## Future Enhancements

### Database Migration
- **PostgreSQL Implementation**: Migrate from CSV-based storage to PostgreSQL database
  - Improved data integrity and ACID transactions
  - Better concurrent access handling
  - Advanced querying and reporting capabilities
  - Automated backups and data recovery
  - Scalability for high-volume operations

### Additional Features
- **Authentication & Authorization**: Implement user roles and permissions
- **Data Analytics Dashboard**: Real-time measurement analytics and reporting
- **API Rate Limiting**: Prevent abuse and ensure fair usage
- **Automated Testing**: Unit tests, integration tests, and load testing
- **Data Export**: Export measurements to various formats (Excel, PDF, JSON)
- **Audit Logging**: Track all data modifications and user actions
- **WebSocket Support**: Real-time updates for measurement data
- **Mobile App Integration**: Enhanced mobile application support
- **Backup & Recovery**: Automated database backup strategies
- **Performance Monitoring**: Application performance metrics and alerting

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and test locally
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check logs: `heroku logs --app project12bvm`
- Monitor performance: Load testing with `load_test.py`

---

**Last Updated**: September 2, 2025
**Version**: 2.0.0
**Status**: Production Ready
