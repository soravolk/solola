import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pytubefix import YouTube
from pydantic import BaseModel

class FileData(BaseModel):
    filename: str
    content_type: str
    data: str  # base64 encoded file data

class Audio(BaseModel):
    source_type: str
    source: str | FileData
    
app = FastAPI()
version = "/api/v1/"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_presigned_url(file_name: str, file_type: str) -> str:
    presigned_url = "presigned_url_placeholder"
    return presigned_url

@app.get("/")
def read_root():
    return {"message": "Hello FastAPI!"}

@app.post(version + "audio")
async def submitAudio(audio: Audio):
    try: 
        if audio.source_type == "youtube":
            yt = YouTube(audio.source)
            return { 
                "id": yt.video_id,
                "name": yt.title
            }
        elif audio.source_type == "local":
            file = audio.source
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(file.filename)[1]
            file_name = f"uploads/{file_id}{file_extension}"
            
            # Generate presigned URL for upload
            presigned_url = generate_presigned_url(file_name, file.content_type)
            
            return {
                "id": file_id,
                "name": file.filename,
                "upload_url": presigned_url
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Unknown audio source type"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process audio: {str(e)}"
        )
