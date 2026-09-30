from pydantic import BaseModel, Field


class BatchCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=3, max_length=50)
    description: str | None = None


class BatchResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None
    status: str
    created_by: str
    
class BatchJoinRequest(BaseModel):
    code: str = Field(min_length=3, max_length=50)


class BatchMemberResponse(BaseModel):
    id: str
    batch_id: str
    student_id: str
    status: str