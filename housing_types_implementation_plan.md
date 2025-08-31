# Housing Types Implementation Plan

## Current State Analysis

### Existing Structure:
- Generic "housing" category with videos in `backend/assets/housing/`
- Blender assets available for all three new housing types
- Current housing measurement schema: `["product_id", "roll_number", "housing_height", "housing_radius", "housing_depth"]`

### New Housing Types to Support:
1. **oval** - Oval housing type
2. **squared** - Square housing type  
3. **angular** - Angular housing type

## Implementation Steps

### 1. File Organization
```python
# Create new directories in backend/assets/
backend/assets/oval_housing/
backend/assets/squared_housing/
backend/assets/angular_housing/

# Move existing blender assets to appropriate locations
# oval_housing_depth.mkv -> backend/assets/oval_housing/depth.mkv
# oval_housing_radius.mkv -> backend/assets/oval_housing/radius.mkv
# sqaure_housing_radius.mkv -> backend/assets/squared_housing/radius.mkv
# square_housing_depth.mkv -> backend/assets/squared_housing/depth.mkv
# angular_housing_depth.mkv -> backend/assets/angular_housing/depth.mkv
# angular_housing_radius.mkv -> backend/assets/angular_housing/radius.mkv
```

### 2. Backend Code Modifications

#### Update VIDEO_DIRS Configuration:
```python
VIDEO_DIRS = {
    "housing": os.path.abspath(os.path.join(assets_dir, "housing")),
    "shaft": os.path.abspath(os.path.join(assets_dir, "shaft")),
    "oval_housing": os.path.abspath(os.path.join(assets_dir, "oval_housing")),
    "squared_housing": os.path.abspath(os.path.join(assets_dir, "squared_housing")),
    "angular_housing": os.path.abspath(os.path.join(assets_dir, "angular_housing")),
}
```

#### Update Housing Measurement Schema:
```python
HOUSING_MEASUREMENT_FIELDS = [
    "product_id", 
    "roll_number", 
    "housing_type",  # NEW FIELD: oval, squared, angular
    "housing_height", 
    "housing_radius", 
    "housing_depth"
]
```

#### Add New Endpoints:
```python
# Get available housing types
@app.get("/housing_types")
def get_housing_types():
    return {
        "housing_types": ["housing", "oval", "squared", "angular"],
        "default": "housing"
    }

# List videos for specific housing type
@app.get("/video/housing_types/{housing_type}")
def list_housing_videos(housing_type: str):
    valid_types = ["oval", "squared", "angular"]
    if housing_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    
    category = f"{housing_type}_housing"
    return await list_videos(category)
```

#### Enhance Housing Measurement Endpoint:
```python
@app.post("/housing_measurement")
def add_housing_measurement(entry: dict = Body(...)):
    ensure_measured_housings_csv_exists()
    
    # Validate required fields including housing_type
    required_fields = HOUSING_MEASUREMENT_FIELDS.copy()
    for field in required_fields:
        if field not in entry:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    # Validate housing_type value
    valid_housing_types = ["housing", "oval", "squared", "angular"]
    if entry["housing_type"] not in valid_housing_types:
        raise HTTPException(status_code=400, detail="Invalid housing type")
    
    from csv_helper import append_csv
    append_csv(get_measured_housings_path(), [entry], HOUSING_MEASUREMENT_FIELDS)
    return {"status": "housing measurement added"}
```

### 3. Backward Compatibility
- Maintain existing "housing" category for legacy support
- Default housing_type to "housing" if not specified in existing data
- Update existing housing measurements to include housing_type="housing"

### 4. Frontend Integration Points
- Add housing type selection UI in frontend
- Update video player to support housing type parameter
- Modify measurement submission to include housing_type
- Add housing type filtering for past measurements

### 5. Testing Strategy
- Test all new endpoints with valid/invalid housing types
- Verify video streaming for each housing type
- Test measurement submission with housing_type field
- Validate backward compatibility with existing data

### 6. Documentation Updates
- Update README.md with new housing type endpoints
- Document new housing_type field in measurement schema
- Add examples for housing type-specific API calls

## Migration Considerations
1. **Data Migration**: Existing housing measurements will need housing_type="housing" added
2. **File Migration**: Move blender assets to new directory structure
3. **Frontend Updates**: Coordinate with frontend team for UI changes
4. **Testing**: Comprehensive testing of all housing type scenarios

## Estimated Implementation Time
- Backend modifications: 2-3 hours
- File reorganization: 1 hour
- Testing and validation: 2 hours
- Documentation: 1 hour

This implementation will provide full support for the three housing types while maintaining complete backward compatibility with existing functionality.
