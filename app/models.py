from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# --- Sensor Models ---

class CreateSensorBase(BaseModel):
    """Base model for Sensor with common fields"""
    name: str = Field(..., max_length=255, description="Sensor name")
    description: str = Field(..., max_length=255, description="Sensor description")
    unit: str = Field(..., max_length=50, description="Unit of measurement")

class SensorBase(BaseModel):
    """Base model for Sensor with common fields"""
    id: int = Field(..., description="Sensor ID")
    name: str = Field(..., max_length=255, description="Sensor name")
    description: str = Field(..., max_length=255, description="Sensor description")
    unit: str = Field(..., max_length=50, description="Unit of measurement")


# --- Sensor Data Models ---

class CreateSensorDataBase(BaseModel):
    """Base model for Sensor Data"""
    sensor_id: int = Field(..., description="ID of the sensor")
    value: float = Field(..., description="Sensor reading value")

class SensorDataBase(BaseModel):
    """Base model for Sensor Data with ID and timestamp"""
    id: int = Field(..., description="Sensor Data ID")
    sensor_id: int = Field(..., description="ID of the sensor")
    value: float = Field(..., description="Sensor reading value")
    timestamp: datetime = Field(..., description="Timestamp of the reading")

