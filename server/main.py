import boto3
import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pytubefix import YouTube
from pydantic import BaseModel

load_dotenv()
class FileData(BaseModel):
    filename: str
    content_type: str

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
    session = boto3.Session(profile_name=os.getenv('AWS_PROFILE'))
    s3_client = session.client('s3')
    bucket_name = os.getenv('S3_BUCKET_NAME')

    try:
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": file_name,
                "ContentType": file_type,
            },
            ExpiresIn=60,  # 1 minute
        )
        return presigned_url
    except Exception as e:
        raise RuntimeError(f"Failed to generate presigned URL: {e}")

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
