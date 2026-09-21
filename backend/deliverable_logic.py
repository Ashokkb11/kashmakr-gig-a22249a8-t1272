from pydantic import ConfigDict
"""
FastAPI health check service with a /health endpoint.
Production-grade implementation with proper validation and error handling.
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
import os
import sys
import platform
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True, extra="allow")
    """Health check response model."""
    status: str = Field(..., description="Overall health status")
    timestamp: str = Field(..., description="ISO format timestamp")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Runtime environment")
    dependencies: Dict[str, str] = Field(..., description="Dependency statuses")
    system: Dict[str, Any] = Field(..., description="System metrics")
    uptime: float = Field(..., description="Service uptime in seconds")


class HealthCheck:
    """Health check service with comprehensive system monitoring."""
    
    def __init__(self, service_name: str = "fastapi-health-service", version: str = "1.0.0"):
        self.service_name = service_name
        self.version = version
        self.start_time = datetime.now()
        self.environment = os.getenv("ENVIRONMENT", "development")
    
    def check_dependencies(self) -> Dict[str, str]:
        """Check critical dependencies and return their status."""
        dependencies = {}
        
        # Check Python version
        dependencies["python"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # Check FastAPI availability
        try:
            import fastapi
            dependencies["fastapi"] = f"ok (v{fastapi.__version__})"
        except ImportError:
            dependencies["fastapi"] = "missing"
        
        # Check Pydantic availability
        try:
            import pydantic
            dependencies["pydantic"] = f"ok (v{pydantic.__version__})"
        except ImportError:
            dependencies["pydantic"] = "missing"
        
        # Check system memory (without psutil)
        try:
            # Simple memory check using os module
            import resource
            memory_info = resource.getrusage(resource.RUSAGE_SELF)
            dependencies["memory"] = f"available: basic check passed"
        except (ImportError, AttributeError):
            # Fallback for Windows or other platforms
            dependencies["memory"] = "basic check"
        
        return dependencies
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Collect system metrics without psutil."""
        metrics = {}
        
        # CPU information
        metrics["cpu_count"] = os.cpu_count()
        
        # Platform information
        metrics["platform"] = platform.platform()
        metrics["python_version"] = platform.python_version()
        
        # Basic system info
        metrics["system"] = platform.system()
        metrics["release"] = platform.release()
        
        # Simple memory estimation (without psutil)
        try:
            import resource
            ru = resource.getrusage(resource.RUSAGE_SELF)
            metrics["memory_usage_mb"] = round(ru.ru_maxrss / 1024, 2)  # Convert to MB
        except (ImportError, AttributeError):
            metrics["memory_usage_mb"] = "unavailable"
        
        # Disk information (basic)
        try:
            import shutil
            disk_usage = shutil.disk_usage("/")
            metrics["disk_total_gb"] = round(disk_usage.total / (1024**3), 2)
            metrics["disk_free_gb"] = round(disk_usage.free / (1024**3), 2)
            metrics["disk_percent_used"] = round((disk_usage.used / disk_usage.total) * 100, 2)
        except (ImportError, OSError):
            metrics["disk_total_gb"] = "unavailable"
            metrics["disk_free_gb"] = "unavailable"
            metrics["disk_percent_used"] = "unavailable"
        
        return metrics
    
    def get_uptime(self) -> float:
        """Calculate service uptime in seconds."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def perform_health_check(self) -> HealthResponse:
        """Perform comprehensive health check and return response."""
        
        # Check dependencies
        dependencies = self.check_dependencies()
        
        # Check if critical dependencies are missing
        critical_deps = ["fastapi", "pydantic"]
        missing_deps = [dep for dep in critical_deps if "missing" in dependencies.get(dep, "")]
        
        # Determine overall status
        if missing_deps:
            status_value = "degraded"
            logger.warning(f"Missing critical dependencies: {missing_deps}")
        else:
            # Check system resources
            system_metrics = self.get_system_metrics()
            
            # Alert if resources are critically low (if available)
            disk_percent = system_metrics.get("disk_percent_used", 0)
            if isinstance(disk_percent, (int, float)) and disk_percent > 90:
                status_value = "degraded"
                logger.warning("Disk usage above 90%")
            else:
                status_value = "healthy"
        
        # Prepare response
        response = HealthResponse(
            status=status_value,
            timestamp=datetime.now().isoformat(),
            service=self.service_name,
            version=self.version,
            environment=self.environment,
            dependencies=dependencies,
            system=self.get_system_metrics(),
            uptime=self.get_uptime()
        )
        
        return response


# Global health check instance
health_checker = HealthCheck()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("Starting FastAPI health check service...")
    yield
    # Shutdown
    logger.info("Shutting down FastAPI health check service...")


# Create FastAPI application
app = FastAPI(
    title="Health Check Service",
    description="A simple health check service with comprehensive system monitoring",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_endpoint(detailed: bool = False) -> HealthResponse:
    """
    Health check endpoint.
    
    Args:
        detailed: If True, includes detailed system metrics
        
    Returns:
        HealthResponse with service health status
    """
    try:
        response = health_checker.perform_health_check()
        
        # If not detailed, remove heavy system metrics
        if not detailed:
            response.system = {
                "cpu_count": response.system.get("cpu_count"),
                "platform": response.system.get("platform"),
                "system": response.system.get("system")
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Health Check Service",
        "version": "1.0.0",
        "endpoints": {
            "/": "Service information",
            "/health": "Health check endpoint (GET)",
            "/docs": "API documentation",
            "/redoc": "Alternative API documentation"
        }
    }


# Export for testing
__all__ = ["app", "HealthCheck", "HealthResponse", "health_checker"]
