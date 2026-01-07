import json
import os
import uuid
import boto3

# Initialize AWS clients outside handler for connection reuse
s3_client = boto3.client('s3')
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'solola-bucket')

def generate_presigned_url(file_name: str, file_type: str) -> str:
    """Generate presigned URL for S3 upload"""
    try:
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": file_name,
                "ContentType": file_type,
            },
            ExpiresIn=60,  # 1 minute
        )
        return presigned_url
    except Exception as e:
        raise RuntimeError(f"Failed to generate presigned URL: {e}")

def lambda_handler(event, context):
    """
    Lambda handler for audio submission API
    
    Generates S3 presigned upload URL for local audio files
    
    API Gateway event format:
    {
        "httpMethod": "POST",
        "path": "/api/v1/audio",
        "body": "{\"source_type\":\"local\",\"source\":{\"filename\":\"test.mp3\",\"content_type\":\"audio/mpeg\"}}"
    }
    """
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',  # Update with your frontend domain in production
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        'Content-Type': 'application/json'
    }
    
    # Handle OPTIONS request (CORS preflight)
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    # Handle GET request (health check)
    if event.get('httpMethod') == 'GET' and event.get('path') == '/':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({"message": "Hello from Lambda!"})
        }
    
    # Handle POST request
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        source_type = body.get('source_type')
        source = body.get('source')
        
        if not source_type:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({"error": "Missing source_type field"})
            }
        
        # Handle local file source
        if source_type == 'local':
            if not isinstance(source, dict):
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({"error": "Local source must be an object with filename and content_type"})
                }
            
            filename = source.get('filename')
            content_type = source.get('content_type')
            
            if not filename or not content_type:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({"error": "Missing filename or content_type"})
                }
            
            # Generate unique file ID and path
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(filename)[1]
            file_name = f"uploads/{file_id}{file_extension}"
            
            # Generate presigned URL for upload
            presigned_url = generate_presigned_url(file_name, content_type)
            
            response_body = {
                "id": file_id,
                "name": filename,
                "upload_url": presigned_url
            }
        
        else:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({"error": f"Unknown audio source type: {source_type}. Only 'local' is supported."})
            }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }
    
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({"error": "Invalid JSON in request body"})
        }
    
    except Exception as e:
        print(f"Error processing request: {str(e)}")  # CloudWatch logs
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({"error": f"Internal server error: {str(e)}"})
        }
