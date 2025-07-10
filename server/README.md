# EG Solo App Server

This is the FastAPI server for the EG Solo App that handles audio file uploads using S3 presigned URLs.

## Setup

1. Install dependencies:

```bash
conda env create -f environment.yml
conda activate solola
```

2. Set up environment variables:
   Create a `.env` file in the server directory with the following variables:

```env
# S3 Configuration
S3_BUCKET_NAME=your-s3-bucket-name
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

## S3 Bucket Setup

1. Create an S3 bucket in your AWS account
2. Configure CORS for your bucket to allow uploads from your frontend domain:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST", "GET"],
    "AllowedOrigins": ["http://localhost:3000", "https://yourdomain.com"],
    "ExposeHeaders": []
  }
]
```

3. Ensure your AWS credentials have the following permissions:
   - `s3:PutObject`
   - `s3:GetObject`
   - `s3:DeleteObject` (optional, for cleanup)

## Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /`: Health check
- `POST /api/v1/audio`: Submit audio file or YouTube URL
  - For local files: Returns a presigned URL for direct S3 upload
  - For YouTube URLs: Returns video metadata

## How it Works

1. Client sends file metadata to `/api/v1/audio`
2. Server generates a unique file ID and S3 presigned URL
3. Server returns the presigned URL to the client
4. Client uploads the file directly to S3 using the presigned URL
5. No files are stored on the server - everything goes directly to S3
