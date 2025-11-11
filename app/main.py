from typing import Union
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .connection import init_db, close_db, get_db
from .models import SensorBase, CreateSensorBase, SensorDataBase, CreateSensorDataBase

app = FastAPI(root_path="/api/1")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Links de donde se permiten requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()
    with get_db() as db:
        # Check if tables exist (sensors and data) and create them if they don't
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS sensors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description VARCHAR(255) NOT NULL,
            unit VARCHAR(50) NOT NULL
        )"""))
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sensor_id INT NOT NULL,
            value FLOAT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sensor_id) REFERENCES sensors(id)
        )"""))


@app.get("/")
def Health():
    """
    Health check endpoint that verifies API and database connectivity.
    
    Returns:
        Dictionary with status of API and database connections.
        Status values: "healthy", "degraded", "error"
    """
    health_status = {
        "api": "healthy",
        "db": "healthy"
    }
    
    try:
        with get_db() as db:
            # Simple ping query to check database connectivity
            db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["db"] = "error"
        health_status["api"] = "degraded"
    
    return health_status

@app.get("/ping")
def ping():
    return {"ping": "pong!"}

@app.get("/pong")
def pong():
    return {"pong": "ping?"}


@app.get("/manage/sensors", response_model=list[SensorBase])
def read_sensors():
    with get_db() as db:
        result = db.execute(text("SELECT * FROM sensors"))
        sensors = result.fetchall()
    return sensors


@app.post("/manage/sensors", response_model=SensorBase, status_code=201)
def create_sensor(sensor: CreateSensorBase):
    with get_db() as db:
        result = db.execute(
            text("INSERT INTO sensors (name, description, unit) VALUES (:name, :description, :unit)"),
            {"name": sensor.name, "description": sensor.description, "unit": sensor.unit}
        )
        sensor_id = result.lastrowid
        
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        new_sensor = result.fetchone()
        
        if not new_sensor:
            raise HTTPException(status_code=500, detail="Failed to create sensor")
            
    return new_sensor


@app.put("/manage/sensors/{sensor_id}", response_model=SensorBase)
def update_sensor(sensor_id: int, sensor: CreateSensorBase):
    with get_db() as db:
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Sensor not found")
        
        db.execute(
            text("UPDATE sensors SET name = :name, description = :description, unit = :unit WHERE id = :id"),
            {"id": sensor_id, "name": sensor.name, "description": sensor.description, "unit": sensor.unit}
        )
        
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        updated_sensor = result.fetchone()
        
    return updated_sensor

@app.get("/manage/sensors/{sensor_id}", response_model=SensorBase)
def get_sensor(sensor_id: int):
    with get_db() as db:
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        sensor = result.fetchone()
        
        if not sensor:
            raise HTTPException(status_code=404, detail="Sensor not found")
            
    return sensor

@app.post("/sensors/{sensor_id}", response_model=SensorDataBase, status_code=201)
def post_sensor_data(sensor_id: int, data: CreateSensorDataBase):
    with get_db() as db:
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Sensor not found")
        
        if data.sensor_id != sensor_id:
            raise HTTPException(status_code=400, detail="Sensor ID mismatch")
        
        result = db.execute(
            text("INSERT INTO sensor_data (sensor_id, value) VALUES (:sensor_id, :value)"),
            {"sensor_id": sensor_id, "value": data.value}
        )
        data_id = result.lastrowid
        
        result = db.execute(text("SELECT * FROM sensor_data WHERE id = :id"), {"id": data_id})
        created_data = result.fetchone()
        
        if not created_data:
            raise HTTPException(status_code=500, detail="Failed to create sensor data")
            
    return created_data

@app.get("/sensors/{sensor_id}", response_model=list[SensorDataBase])
def get_sensor_data(sensor_id: int, from_timestamp: Union[str, None] = None, to_timestamp: Union[str, None] = None):
    with get_db() as db:
        result = db.execute(text("SELECT * FROM sensors WHERE id = :id"), {"id": sensor_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Sensor not found")
        
        query = "SELECT * FROM sensor_data WHERE sensor_id = :sensor_id"
        params = {"sensor_id": sensor_id}
        
        if from_timestamp:
            query += " AND timestamp >= :from_timestamp"
            params["from_timestamp"] = from_timestamp
        if to_timestamp:
            query += " AND timestamp <= :to_timestamp"
            params["to_timestamp"] = to_timestamp
            
        query += " ORDER BY timestamp DESC"
        
        result = db.execute(text(query), params)
        data = result.fetchall()
        
    return data

@app.post("/sensors/", response_model=dict[int, list[SensorDataBase]])
def post_multiple_sensor_data(data_list: list[CreateSensorDataBase]):
    if not data_list:
        return {}
    
    with get_db() as db:
        # Get unique sensor IDs and validate they all exist
        sensor_ids = set(data.sensor_id for data in data_list)
        placeholders = ", ".join([f":sensor_id_{i}" for i in range(len(sensor_ids))])
        params = {f"sensor_id_{i}": sid for i, sid in enumerate(sensor_ids)}
        
        result = db.execute(
            text(f"SELECT id FROM sensors WHERE id IN ({placeholders})"),
            params
        )
        existing_sensors = {row[0] for row in result.fetchall()}
        
        # Check for non-existent sensors
        missing_sensors = sensor_ids - existing_sensors
        if missing_sensors:
            raise HTTPException(
                status_code=404, 
                detail=f"Sensors not found: {sorted(missing_sensors)}"
            )
        
        # Build bulk INSERT query
        values_placeholders = ", ".join([
            f"(:sensor_id_{i}, :value_{i})" 
            for i in range(len(data_list))
        ])
        
        insert_params = {}
        for i, data in enumerate(data_list):
            insert_params[f"sensor_id_{i}"] = data.sensor_id
            insert_params[f"value_{i}"] = data.value
        
        # Execute bulk insert
        db.execute(
            text(f"""
                INSERT INTO sensor_data (sensor_id, value) 
                VALUES {values_placeholders}
            """),
            insert_params
        )
        
        # Fetch all inserted records (MySQL doesn't return IDs from bulk insert easily)
        # So we fetch the most recent records for each sensor
        result = db.execute(
            text(f"""
                SELECT sd.* 
                FROM sensor_data sd
                INNER JOIN (
                    SELECT sensor_id, MAX(timestamp) as max_ts
                    FROM sensor_data
                    WHERE sensor_id IN ({placeholders})
                    GROUP BY sensor_id
                ) latest ON sd.sensor_id = latest.sensor_id 
                    AND sd.timestamp = latest.max_ts
                ORDER BY sd.sensor_id, sd.id DESC
            """),
            params
        )
        inserted_data = result.fetchall()
        
        # Group by sensor_id
        response = {}
        for row in inserted_data:
            sensor_id = row.sensor_id
            if sensor_id not in response:
                response[sensor_id] = []
            response[sensor_id].append(row)
            
    return response

@app.get("/sensors/", response_model=dict[int, list[SensorDataBase]])
def get_all_sensor_data(from_timestamp: Union[str, None] = None, to_timestamp: Union[str, None] = None):
    with get_db() as db:
        query = "SELECT * FROM sensor_data WHERE 1=1"
        params = {}
        if from_timestamp:
            query += " AND timestamp >= :from_timestamp"
            params["from_timestamp"] = from_timestamp
        if to_timestamp:
            query += " AND timestamp <= :to_timestamp"
            params["to_timestamp"] = to_timestamp

        query += " ORDER BY timestamp DESC"

        result = db.execute(text(query), params)
        data = result.fetchall()
        
        # Group by sensor_id
        response = {}
        for row in data:
            sensor_id = row.sensor_id
            if sensor_id not in response:
                response[sensor_id] = []
            response[sensor_id].append(row)
            
    return response

@app.on_event("shutdown")
async def shutdown_event():
    close_db()