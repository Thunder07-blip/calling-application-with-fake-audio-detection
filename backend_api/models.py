from pydantic import BaseModel, Field

class TokenResponse(BaseModel):
    token: str = Field(..., description="The generated JWT token for LiveKit")
    livekit_url: str = Field(..., description="The URL to connect to the LiveKit server")
