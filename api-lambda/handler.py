import json
import os
import uuid
import boto3
from botocore.config import Config
from datetime import datetime, timedelta
from transpose import parse_transpose_semitones, transpose_musicxml
from edit_router import run_router
from edit_executor import edit_with_repair
from edit_response import build_response
from musicxml_validate import count_notes

# Initialize AWS clients outside handler for connection reuse
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
# Cap each Bedrock call below the API Gateway ~30s timeout so a slow Editor
# rewrite aborts in time for a graceful reply instead of a raw 503.
_bedrock_cfg = Config(connect_timeout=5, read_timeout=25,
                      retries={'max_attempts': 1, 'mode': 'standard'})
bedrock_client = boto3.client('bedrock-runtime',
                              region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                              config=_bedrock_cfg)
dynamodb = boto3.resource('dynamodb')
rate_limit_table = dynamodb.Table(os.environ.get('RATE_LIMIT_TABLE', 'solola-rate-limit'))

BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'solola-bucket')
INFERENCE_LAMBDA_ARN = os.environ.get('INFERENCE_LAMBDA_ARN', '')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'openai.gpt-oss-20b-1:0')

# Rate limit config
MAX_FIX_REQUESTS_PER_HOUR = int(os.environ.get('MAX_FIX_REQUESTS_PER_HOUR', '20'))
MAX_FIX_REQUESTS_PER_DAY = int(os.environ.get('MAX_FIX_REQUESTS_PER_DAY', '100'))


# ---------------------------------------------------------------------------

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
    
    # CORS headers - reflect the request origin if it's in the allowed list
    allowed_origins = {
        'https://solola.net',
        'https://www.solola.net',
        'http://localhost:5173',
    }
    request_origin = event.get('headers', {}).get('origin', '')
    cors_origin = request_origin if request_origin in allowed_origins else 'https://solola.net'
    headers = {
        'Access-Control-Allow-Origin': cors_origin,
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
            source_type = body.get('source_type', 'local')  # 'local' or 'youtube'
            youtube_url = body.get('youtube_url')  # For YouTube sources
            
            if not file_id or not filename:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({'error': 'Missing file_id or filename'})
                }
            
            print(f"Processing generation request - File ID: {file_id}, User ID: {user_id}, Source: {source_type}")
            
            inference_payload = {
                "bucket": BUCKET_NAME,
                "user_id": user_id,
                "source_type": source_type
            }
            
            # Handle local file source
            if source_type == 'local':
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
                
                inference_payload["audio_key"] = audio_key
            
            # Handle YouTube source
            elif source_type == 'youtube':
                if not youtube_url:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': 'Missing youtube_url for YouTube source'})
                    }
                
                inference_payload["youtube_url"] = youtube_url
                inference_payload["video_id"] = file_id
            
            else:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({"error": f"Unknown source type: {source_type}"})
                }
            
            # Invoke inference Lambda asynchronously
            # Pass userId to inference Lambda so it can forward to ECS
            
            response = lambda_client.invoke(
                FunctionName=INFERENCE_LAMBDA_ARN,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(inference_payload)
            )
            
            response_body = {
                "status": "PENDING",
                "message": "Inference task started",
                "file_id": file_id,
                "user_id": user_id,
                "source_type": source_type
            }
            
            if source_type == 'local':
                response_body["audio_key"] = inference_payload["audio_key"]
            elif source_type == 'youtube':
                response_body["youtube_url"] = youtube_url
            
            return {
                'statusCode': 202,
                'headers': headers,
                'body': json.dumps(response_body)
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
            
            # Handle YouTube link source
            elif source_type == 'youtube':
                if not isinstance(source, str):
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({"error": "YouTube source must be a URL string"})
                    }
                
                # Extract video ID from YouTube URL
                # Supports formats: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
                video_id = None
                if 'youtube.com/watch?v=' in source:
                    video_id = source.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in source:
                    video_id = source.split('youtu.be/')[1].split('?')[0]
                elif 'youtube.com/embed/' in source:
                    video_id = source.split('embed/')[1].split('?')[0]
                
                if not video_id:
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({"error": "Invalid YouTube URL format"})
                    }
                
                response_body = {
                    "id": video_id,
                    "name": f"YouTube Video {video_id}",
                    "source_type": "youtube",
                    "youtube_url": source
                }
            
            else:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({"error": f"Unknown audio source type: {source_type}. Supported types: 'local', 'youtube'."})
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
    
    # Route: POST /api/v1/fix - conversational Router -> Edit pipeline
    if http_method == 'POST' and request_path == '/api/v1/fix':
        print(">>> Matched /api/v1/fix route")
        try:
            body = json.loads(event.get('body', '{}'))
            current_xml = body.get('currentXml', '')
            instruction = body.get('instruction', '')
            history = body.get('history', []) or []

            source_ip = event.get('requestContext', {}).get('http', {}).get('sourceIp', 'unknown')

            if not instruction:
                return {'statusCode': 400, 'headers': headers,
                        'body': json.dumps({'error': 'Missing instruction'})}

            rate_check = check_rate_limit(source_ip)
            if not rate_check['allowed']:
                return {'statusCode': 429, 'headers': headers,
                        'body': json.dumps({'error': rate_check['error']})}

            MAX_XML_SIZE = 500_000
            MAX_INSTRUCTION_SIZE = 1000
            if len(current_xml) > MAX_XML_SIZE:
                return {'statusCode': 413, 'headers': headers,
                        'body': json.dumps({'error': f'XML too large (max {MAX_XML_SIZE} bytes)'})}
            if len(instruction) > MAX_INSTRUCTION_SIZE:
                return {'statusCode': 413, 'headers': headers,
                        'body': json.dumps({'error': f'Instruction too long (max {MAX_INSTRUCTION_SIZE} chars)'})}

            has_transcription = bool(current_xml)
            original_note_count = count_notes(current_xml)

            # --- Fast path: deterministic transpose (no LLM, never times out) ---
            # Runs BEFORE the Router so obvious transposes bypass the slow Editor
            # rewrite entirely and cannot hit the API Gateway ~30s timeout.
            if has_transcription:
                fast_semitones = parse_transpose_semitones(instruction)
                if fast_semitones is not None:
                    transposed = transpose_musicxml(current_xml, fast_semitones)
                    direction = 'up' if fast_semitones > 0 else 'down'
                    return {'statusCode': 200, 'headers': headers,
                            'body': json.dumps(build_response('transpose',
                                f"Transposed {direction} {abs(fast_semitones)} semitone(s).",
                                xml_content=transposed))}

            # --- Router (no XML; cheap) ---
            routed = run_router(bedrock_client, BEDROCK_MODEL_ID, history,
                                instruction, has_transcription)
            intent = routed['intent']
            reply = routed['reply']
            print(f"Router intent={intent} ip={source_ip} instr={instruction[:80]!r}")

            # --- clarify / reject: reply only, no XML ---
            if intent in ('clarify', 'reject'):
                if not reply:
                    reply = ("Could you be more specific about which note or change you want?"
                             if intent == 'clarify'
                             else "I can change notes, rhythm, articulations, transpose, or restore the original - but not that.")
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response(intent, reply))}

            # --- restore: signal client-side swap ---
            if intent == 'restore':
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('restore', reply or "Restored the original transcription."))}

            # Everything below needs a current transcription.
            if not has_transcription:
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('reject',
                            "Please generate a transcription first, then I can edit it."))}

            # --- transpose: deterministic ---
            if intent == 'transpose':
                semitones = routed['semitones']
                if semitones is None:
                    semitones = parse_transpose_semitones(instruction)
                if semitones is None:
                    return {'statusCode': 200, 'headers': headers,
                            'body': json.dumps(build_response('clarify',
                                "How many semitones should I transpose, and up or down?"))}
                transposed = transpose_musicxml(current_xml, semitones)
                direction = 'up' if semitones > 0 else 'down'
                msg = reply or f"Transposed {direction} {abs(semitones)} semitone(s)."
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('transpose', msg, xml_content=transposed))}

            # --- edit: Editor + validate/repair (wall-clock budgeted in executor) ---
            ok, fixed_xml, err = edit_with_repair(
                bedrock_client, BEDROCK_MODEL_ID, current_xml, instruction,
                original_note_count)
            if ok:
                msg = reply or "Done - updated the transcription."
                return {'statusCode': 200, 'headers': headers,
                        'body': json.dumps(build_response('edit', msg, xml_content=fixed_xml))}
            print(f"Edit failed: {err}")
            if err and 'timed out' in err.lower():
                fail_msg = ("That edit took too long to apply on a transcription this "
                            "size. Try a smaller, more specific change - transposing is instant.")
            else:
                fail_msg = "I couldn't apply that cleanly - try rephrasing or being more specific."
            return {'statusCode': 200, 'headers': headers,
                    'body': json.dumps(build_response('reject', fail_msg))}

        except Exception as e:
            print(f"Error in /api/v1/fix: {str(e)}")
            return {'statusCode': 500, 'headers': headers,
                    'body': json.dumps({'error': f'Edit failed: {str(e)}'})}

    # No route matched - return 404
    return {
        'statusCode': 404,
        'headers': headers,
        'body': json.dumps({
            "error": "Not Found",
            "message": f"No route matches {http_method} {request_path}"
        })
    }
