from fastapi import FastAPI, HTTPException
from pytubefix import YouTube
from pydantic import BaseModel

class Audio(BaseModel):
    source_type: str
    url: str
    
app = FastAPI()
version = "/api/v1/"

@app.get("/")
def read_root():
    return {"message": "Hello FastAPI!"}

@app.post(version + "audio")
def submitAudio(audio: Audio):
    try: 
        if audio.source_type == "youtube":
            yt = YouTube(audio.url)
            return { "title": yt.title}
        else:
            raise HTTPException(
                status_code=400,
                detail="Unknown audio source type"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process YouTube video: {str(e)}"
        )
