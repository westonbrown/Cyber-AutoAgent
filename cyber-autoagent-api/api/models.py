from pydantic import BaseModel

class JobCreate(BaseModel):
    target: str
    objective: str

class JobResponse(BaseModel):
    job_id: str
    status: str
