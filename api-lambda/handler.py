import json
import os
import uuid
import boto3

# Initialize AWS clients outside handler for connection reuse
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'solola-bucket')
INFERENCE_LAMBDA_ARN = os.environ.get('INFERENCE_LAMBDA_ARN', '')

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
    """Handle API Gateway requests"""
    
    # Debug logging
    print(f"=== LAMBDA HANDLER INVOKED ===")
    print(f"Full event: {json.dumps(event)}")
    
    # Extract path and method with fallback
    request_path = event.get('rawPath') or event.get('path', '')
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', '')
    
    print(f"Extracted path: {request_path}")
    print(f"Extracted method: {http_method}")
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        'Content-Type': 'application/json'
    }
    
    # Handle OPTIONS (CORS preflight)
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    # Route: POST /api/v1/generate - Trigger inference
    if http_method == 'POST' and request_path == '/api/v1/generate':
        print(">>> Matched /api/v1/generate route")
        try:
            body = json.loads(event.get('body', '{}'))
            print(f"Request body: {body}")
            
            file_id = body.get('file_id')
            filename = body.get('filename')
            
            if not file_id or not filename:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Missing file_id or filename'})
                }
            
            # Determine file extension from filename
            file_extension = os.path.splitext(filename)[1] if filename else '.mp3'
            audio_key = f"uploads/{file_id}{file_extension}"
            
            # Verify file exists in S3
            try:
                s3_client.head_object(Bucket=BUCKET_NAME, Key=audio_key)
            except Exception as e:
                return {
                    'statusCode': 404,
                    'headers': headers,
                    'body': json.dumps({"error": f"Audio file not found: {audio_key}", "details": str(e)})
                }
            
            # Invoke inference Lambda asynchronously
            # The inference Lambda expects: { "audio_key": "uploads/...", "bucket": "..." }
            inference_payload = {
                "audio_key": audio_key,
                "bucket": BUCKET_NAME
            }
            
            response = lambda_client.invoke(
                FunctionName=INFERENCE_LAMBDA_ARN,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(inference_payload)
            )
            
            return {
                'statusCode': 202,
                'headers': headers,
                'body': json.dumps({
                    "status": "PENDING",
                    "message": "Inference task started",
                    "file_id": file_id,
                    "audio_key": audio_key
                })
            }
            
        except Exception as e:
            print(f"Error triggering inference: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({"error": f"Failed to trigger inference: {str(e)}"})
            }
    
    # Handle POST request for presigned URL
    if http_method == 'POST' and request_path == '/api/v1/audio':
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
    
    # No route matched - return 404
    return {
        'statusCode': 404,
        'headers': headers,
        'body': json.dumps({
            "error": "Not Found",
            "message": f"No route matches {http_method} {request_path}"
        })
    }
