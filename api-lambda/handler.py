import json
import os
import uuid
import boto3
from datetime import datetime, timedelta

# Initialize AWS clients outside handler for connection reuse
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb')
rate_limit_table = dynamodb.Table(os.environ.get('RATE_LIMIT_TABLE', 'solola-rate-limit'))

BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'solola-bucket')
INFERENCE_LAMBDA_ARN = os.environ.get('INFERENCE_LAMBDA_ARN', '')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'openai.gpt-oss-20b-1:0')

# Rate limit config
MAX_FIX_REQUESTS_PER_HOUR = int(os.environ.get('MAX_FIX_REQUESTS_PER_HOUR', '20'))
MAX_FIX_REQUESTS_PER_DAY = int(os.environ.get('MAX_FIX_REQUESTS_PER_DAY', '100'))

def check_rate_limit(identifier: str) -> dict:
    """Check if IP/user has exceeded rate limits. Returns {'allowed': bool, 'error': str}"""
    now = datetime.utcnow()
    hour_key = now.strftime('%Y%m%d%H')
    day_key = now.strftime('%Y%m%d')
    
    try:
        response = rate_limit_table.get_item(Key={'user_id': identifier})
        
        if 'Item' not in response:
            # First request from this identifier
            rate_limit_table.put_item(Item={
                'user_id': identifier,
                'hourly': {hour_key: 1},
                'daily': {day_key: 1},
                'expires_at': int((now + timedelta(days=2)).timestamp())
            })
            return {'allowed': True}
        
        item = response['Item']
        hourly = item.get('hourly', {})
        daily = item.get('daily', {})
        
        hourly_count = hourly.get(hour_key, 0)
        daily_count = daily.get(day_key, 0)
        
        # Check limits
        if hourly_count >= MAX_FIX_REQUESTS_PER_HOUR:
            return {
                'allowed': False,
                'error': f'Rate limit exceeded: {MAX_FIX_REQUESTS_PER_HOUR} requests per hour. Please try again later.'
            }
        
        if daily_count >= MAX_FIX_REQUESTS_PER_DAY:
            return {
                'allowed': False,
                'error': f'Rate limit exceeded: {MAX_FIX_REQUESTS_PER_DAY} requests per day. Please try again tomorrow.'
            }
        
        # Update counts
        hourly[hour_key] = hourly_count + 1
        daily[day_key] = daily_count + 1
        
        rate_limit_table.put_item(Item={
            'user_id': identifier,
            'hourly': hourly,
            'daily': daily,
            'expires_at': int((now + timedelta(days=2)).timestamp())
        })
        
        return {'allowed': True}
        
    except Exception as e:
        print(f"Rate limit check error: {e}")
        # Fail open - allow request if rate limit check fails
        return {'allowed': True}

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
            user_id = body.get('user_id', 'anonymous')  # Accept userId from frontend
            
            if not file_id or not filename:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Missing file_id or filename'})
                }
            
            print(f"Processing generation request - File ID: {file_id}, User ID: {user_id}")
            
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
            # Pass userId to inference Lambda so it can forward to ECS
            inference_payload = {
                "audio_key": audio_key,
                "bucket": BUCKET_NAME,
                "user_id": user_id  # Pass userId to inference Lambda
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
                    "audio_key": audio_key,
                    "user_id": user_id  # Return userId for confirmation
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
    
    # Route: POST /api/v1/fix - AI-powered MusicXML correction via Bedrock
    if http_method == 'POST' and request_path == '/api/v1/fix':
        print(">>> Matched /api/v1/fix route")
        try:
            body = json.loads(event.get('body', '{}'))
            current_xml = body.get('currentXml', '')
            instruction = body.get('instruction', '')
            
            # Extract source IP for rate limiting
            source_ip = event.get('requestContext', {}).get('http', {}).get('sourceIp', 'unknown')

            if not current_xml or not instruction:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Missing currentXml or instruction'})
                }

            # Abuse protection: IP-based rate limiting
            rate_check = check_rate_limit(source_ip)
            if not rate_check['allowed']:
                return {
                    'statusCode': 429,
                    'headers': headers,
                    'body': json.dumps({'error': rate_check['error']})
                }

            # Abuse protection: size limits
            MAX_XML_SIZE = 500_000  # 500KB
            MAX_INSTRUCTION_SIZE = 1000  # 1000 chars
            
            if len(current_xml) > MAX_XML_SIZE:
                return {
                    'statusCode': 413,
                    'headers': headers,
                    'body': json.dumps({'error': f'XML too large (max {MAX_XML_SIZE} bytes)'})
                }
            
            if len(instruction) > MAX_INSTRUCTION_SIZE:
                return {
                    'statusCode': 413,
                    'headers': headers,
                    'body': json.dumps({'error': f'Instruction too long (max {MAX_INSTRUCTION_SIZE} chars)'})
                }

            print(f"Fix request - IP: {source_ip}, instruction: {instruction[:100]}")

            # Call Bedrock with the Converse API
            response = bedrock_client.converse(
                modelId=BEDROCK_MODEL_ID,
                system=[{
                    'text': (
                        'You are a MusicXML editing assistant for guitar transcriptions. '
                        'The user will give you a MusicXML document and a change request. '
                        'Apply the requested changes accurately and return ONLY the complete '
                        'corrected MusicXML document. No explanation, no markdown fences, '
                        'no extra text — just the raw XML starting with <?xml.'
                    )
                }],
                messages=[{
                    'role': 'user',
                    'content': [{
                        'text': (
                            f'Here is the current MusicXML:\n\n{current_xml}\n\n'
                            f'Please make this change: {instruction}'
                        )
                    }]
                }],
                inferenceConfig={
                    'temperature': 0,
                    'maxTokens': 8192,
                },
            )

            fixed_xml = response['output']['message']['content'][0]['text'].strip()

            # Strip markdown fences if the model wraps them anyway
            if fixed_xml.startswith('```'):
                fixed_xml = fixed_xml.split('\n', 1)[1]  # remove first line
                if fixed_xml.endswith('```'):
                    fixed_xml = fixed_xml[:-3].rstrip()

            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'xmlContent': fixed_xml})
            }

        except Exception as e:
            print(f"Error in /api/v1/fix: {str(e)}")
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({'error': f'AI fix failed: {str(e)}'})
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
