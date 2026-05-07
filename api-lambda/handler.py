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

# ---------------------------------------------------------------------------
# Deterministic transpose helpers (no AI needed)
# ---------------------------------------------------------------------------

# Chromatic semitone within an octave for each step
_STEP_TO_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# Prefer sharps when converting back
_SEMI_TO_PITCH = {
    0: ('C', 0), 1: ('C', 1),  2: ('D', 0), 3: ('D', 1),  4: ('E', 0),
    5: ('F', 0), 6: ('F', 1),  7: ('G', 0), 8: ('G', 1),  9: ('A', 0),
    10: ('A', 1), 11: ('B', 0),
}

# Guitar standard tuning: string number -> open-string MIDI note
_GUITAR_OPEN_MIDI = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}


def _pitch_to_midi(step: str, alter: int, octave: int) -> int:
    return (octave + 1) * 12 + _STEP_TO_SEMI[step] + alter


def _midi_to_pitch(midi: int):
    octave = (midi // 12) - 1
    step, alter = _SEMI_TO_PITCH[midi % 12]
    return step, alter, octave


def parse_transpose_semitones(instruction: str):
    """
    Detect a transpose instruction and return the semitone count as an int
    (positive = up, negative = down).  Returns None if not a transpose request.
    """
    import re as _re
    text = instruction.lower()

    transpose_keywords = [
        'transpose', 'transpos', 'half-step', 'half step', 'semitone',
        'raise', 'lower', 'shift up', 'shift down', 'move up', 'move down',
        'pitch up', 'pitch down', 'key up', 'key down',
    ]
    if not any(k in text for k in transpose_keywords):
        return None

    num_match = _re.search(r'\b(\d+)\b', text)
    n = int(num_match.group(1)) if num_match else 1

    down_keywords = ['down', 'lower', 'flat', 'decrease', 'minus', '-']
    if any(k in text for k in down_keywords):
        return -n
    return n


def transpose_musicxml(xml_string: str, semitones: int) -> str:
    """Transpose every pitch (and guitar fret) in *xml_string* by *semitones*."""
    import re as _re

    def _transpose_pitch_block(pitch_xml: str) -> str:
        step_m   = _re.search(r'<step>([A-G])</step>', pitch_xml)
        alter_m  = _re.search(r'<alter>([-\d.]+)</alter>', pitch_xml)
        octave_m = _re.search(r'<octave>(\d+)</octave>', pitch_xml)
        if not step_m or not octave_m:
            return pitch_xml

        step   = step_m.group(1)
        alter  = int(round(float(alter_m.group(1)))) if alter_m else 0
        octave = int(octave_m.group(1))

        new_midi                    = _pitch_to_midi(step, alter, octave) + semitones
        new_step, new_alter, new_oct = _midi_to_pitch(new_midi)

        result = _re.sub(r'<step>[A-G]</step>',
                         f'<step>{new_step}</step>', pitch_xml)
        result = _re.sub(r'<octave>\d+</octave>',
                         f'<octave>{new_oct}</octave>', result)

        if new_alter != 0:
            alter_tag = f'<alter>{new_alter}</alter>'
            if alter_m:
                result = _re.sub(r'<alter>[-\d.]+</alter>', alter_tag, result)
            else:
                result = _re.sub(r'(</step>)', r'\1' + alter_tag, result, count=1)
        else:
            result = _re.sub(r'\s*<alter>[-\d.]+</alter>', '', result)

        return result

    def _transpose_note(note_xml: str) -> str:
        # 1. Update <pitch> block
        new_note = _re.sub(
            r'<pitch>.*?</pitch>',
            lambda m: _transpose_pitch_block(m.group(0)),
            note_xml, flags=_re.DOTALL,
        )

        # 2. Update <fret> (guitar tab notation)
        string_m = _re.search(r'<string>(\d+)</string>', new_note)
        fret_m   = _re.search(r'<fret>(\d+)</fret>',    new_note)
        if not (string_m and fret_m):
            return new_note

        string_num = int(string_m.group(1))

        # Extract new pitch MIDI from the already-updated <pitch> block
        pitch_m = _re.search(r'<pitch>(.*?)</pitch>', new_note, _re.DOTALL)
        if not pitch_m:
            return new_note
        step_m2   = _re.search(r'<step>([A-G])</step>',    pitch_m.group(1))
        alter_m2  = _re.search(r'<alter>([-\d.]+)</alter>', pitch_m.group(1))
        octave_m2 = _re.search(r'<octave>(\d+)</octave>',  pitch_m.group(1))
        if not (step_m2 and octave_m2):
            return new_note

        new_step2  = step_m2.group(1)
        new_alter2 = int(round(float(alter_m2.group(1)))) if alter_m2 else 0
        new_oct2   = int(octave_m2.group(1))
        new_midi   = _pitch_to_midi(new_step2, new_alter2, new_oct2)

        # Try same string first
        new_fret = new_midi - _GUITAR_OPEN_MIDI.get(string_num, 0)
        new_string = string_num

        if new_fret < 0:
            # Move to a higher-pitched (lower-numbered) string
            for s in range(string_num - 1, 0, -1):
                candidate = new_midi - _GUITAR_OPEN_MIDI[s]
                if 0 <= candidate <= 24:
                    new_fret, new_string = candidate, s
                    break
            else:
                new_fret = 0  # can't represent on standard guitar – clamp

        elif new_fret > 24:
            # Move to a lower-pitched (higher-numbered) string
            for s in range(string_num + 1, 7):
                candidate = new_midi - _GUITAR_OPEN_MIDI[s]
                if 0 <= candidate <= 24:
                    new_fret, new_string = candidate, s
                    break

        if new_string != string_num:
            new_note = _re.sub(r'<string>\d+</string>',
                               f'<string>{new_string}</string>',
                               new_note, count=1)
        new_note = _re.sub(r'<fret>\d+</fret>',
                           f'<fret>{max(0, new_fret)}</fret>',
                           new_note, count=1)
        return new_note

    return _re.sub(
        r'<note>.*?</note>',
        lambda m: _transpose_note(m.group(0)),
        xml_string, flags=_re.DOTALL,
    )


# ---------------------------------------------------------------------------

def _classify_intent(instruction: str, client, model_id: str) -> str:
    """
    Use a cheap Bedrock call (no XML) to classify the user's instruction into
    one of: 'restore_original' | 'transpose' | 'fix'.
    Falls back to 'fix' on any error so the full AI path is always a safe default.
    """
    prompt = (
        "Classify the following guitar transcription edit request into EXACTLY one of "
        "these intents:\n"
        "  restore_original – the user wants the transcription reverted to its original state\n"
        "  transpose        – the user wants all notes shifted up or down by semitones/half-steps\n"
        "  fix              – any other edit (e.g. correct a note, change rhythm, add articulation)\n\n"
        f"Request: \"{instruction}\"\n\n"
        "Reply with a single JSON object and nothing else: "
        "{\"intent\": \"<restore_original|transpose|fix>\"}"
    )
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{'role': 'user', 'content': [{'text': prompt}]}],
            inferenceConfig={'temperature': 0, 'maxTokens': 32},
        )
        text = response['output']['message']['content'][0]['text'].strip()
        import re as _re
        m = _re.search(r'"intent"\s*:\s*"(restore_original|transpose|fix)"', text)
        return m.group(1) if m else 'fix'
    except Exception as e:
        print(f"Intent classification failed: {e}")
        return 'fix'


def _classify_transpose_semitones(instruction: str, client, model_id: str):
    """
    Ask the model to extract the semitone count from a transpose instruction.
    Returns a signed int or None on failure.
    """
    prompt = (
        "Extract the transposition amount from this guitar instruction.\n"
        f"Instruction: \"{instruction}\"\n\n"
        "Reply with a single JSON object: "
        "{\"semitones\": <signed integer, positive=up, negative=down>}\n"
        "If you cannot determine the amount, reply {\"semitones\": null}."
    )
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{'role': 'user', 'content': [{'text': prompt}]}],
            inferenceConfig={'temperature': 0, 'maxTokens': 32},
        )
        text = response['output']['message']['content'][0]['text'].strip()
        import re as _re, json as _json
        m = _re.search(r'\{.*?\}', text, _re.DOTALL)
        if m:
            val = _json.loads(m.group(0)).get('semitones')
            return int(val) if val is not None else None
    except Exception as e:
        print(f"Transpose semitone classification failed: {e}")
    return None


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

            # --- Fast path 1: deterministic transpose (no AI needed) ---
            transpose_semitones = parse_transpose_semitones(instruction)
            if transpose_semitones is not None:
                print(f"Detected transpose request: {transpose_semitones} semitone(s)")
                transposed_xml = transpose_musicxml(current_xml, transpose_semitones)
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({'xmlContent': transposed_xml})
                }

            # --- Fast path 2: cheap intent classification (no XML sent) ---
            # For instructions not caught by regex, ask a small model to classify
            # the intent. The prompt contains NO XML, so it never hits token limits.
            # Only proceed to the full XML-rewrite call when intent == "fix".
            detected_intent = _classify_intent(instruction, bedrock_client, BEDROCK_MODEL_ID)
            print(f"Classified intent: {detected_intent}")

            if detected_intent == 'restore_original':
                # Signal the frontend to restore; actual XML swap happens client-side.
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps({'intent': 'restore_original'})
                }

            if detected_intent == 'transpose':
                # Regex missed it — ask the classifier for the direction/amount too.
                semitones = _classify_transpose_semitones(instruction, bedrock_client, BEDROCK_MODEL_ID)
                if semitones is not None:
                    transposed_xml = transpose_musicxml(current_xml, semitones)
                    return {
                        'statusCode': 200,
                        'headers': headers,
                        'body': json.dumps({'xmlContent': transposed_xml})
                    }
                # Fall through to full AI edit if we still can't parse it.

            # detected_intent == 'fix' (or unknown) → full XML rewrite via Bedrock
            system_prompt = (
                'You are a MusicXML editing assistant for guitar transcriptions. '
                'The user will give you a MusicXML document and a change request. '
                'Apply the requested changes accurately and return ONLY the complete '
                'corrected MusicXML document. No explanation, no markdown fences, '
                'no extra text — just the raw XML starting with <?xml.\n\n'
                'IMPORTANT: Guitar standard tuning open string pitches (fret 0):\n'
                '  String 1 (high E) = E4\n'
                '  String 2 = B3\n'
                '  String 3 = G3\n'
                '  String 4 = D3\n'
                '  String 5 = A2\n'
                '  String 6 (low E) = E2\n\n'
                'Each fret raises the pitch by one semitone. The chromatic scale is: '
                'C, C#/Db, D, D#/Eb, E, F, F#/Gb, G, G#/Ab, A, A#/Bb, B. '
                'The octave increments after B (i.e., B4 -> C5).\n\n'
                'When changing <string> or <fret>, you MUST recalculate and update '
                'the <pitch> element (<step>, <alter>, <octave>) to match the new '
                'string and fret. For example:\n'
                '  String 2, Fret 12 = B4 (step=B, octave=4)\n'
                '  String 1, Fret 13 = F5 (step=F, octave=5)\n'
                '  String 3, Fret 9 = E4 (step=E, octave=4)\n'
                'Use <alter>-1</alter> for flats and <alter>1</alter> for sharps.'
            )

            user_prompt = (
                f'Here is the current MusicXML:\n\n{current_xml}\n\n'
                f'Please make this change: {instruction}'
            )

            # Call Bedrock Converse API (no retries — keep it fast within 30s API Gateway limit)
            fixed_xml = None

            try:
                response = bedrock_client.converse(
                    modelId=BEDROCK_MODEL_ID,
                    system=[{'text': system_prompt}],
                    messages=[{
                        'role': 'user',
                        'content': [{'text': user_prompt}]
                    }],
                    inferenceConfig={
                        'temperature': 0,
                        'maxTokens': 8192,
                    },
                )
                print(f"Converse response keys: {list(response.keys())}")

                # Robustly extract text from Converse response
                try:
                    output_msg = response.get('output', {}).get('message', {})
                    content_list = output_msg.get('content', [])
                    print(f"Converse content structure: {[{k: type(v).__name__ for k, v in item.items()} if isinstance(item, dict) else type(item).__name__ for item in content_list]}")

                    for item in content_list:
                        if isinstance(item, dict):
                            if 'text' in item:
                                fixed_xml = item['text'].strip()
                                break
                            # Some models return content differently
                            for key in ('body', 'value', 'content'):
                                if key in item:
                                    fixed_xml = str(item[key]).strip()
                                    break
                        elif isinstance(item, str):
                            fixed_xml = item.strip()
                            break
                        if fixed_xml:
                            break

                    if not fixed_xml:
                        # Last resort: dump content for debugging
                        print(f"Could not extract text from content: {json.dumps(content_list, default=str)[:1000]}")
                        # Try entire output as string
                        raw = json.dumps(response.get('output', {}), default=str)
                        if '<?xml' in raw:
                            import re as _re
                            m = _re.search(r'(<\?xml.*?</score-partwise>)', raw, _re.DOTALL)
                            if m:
                                fixed_xml = m.group(1).strip()
                                print("Extracted XML from raw output dump")

                except Exception as parse_err:
                    print(f"Error parsing Converse response: {parse_err}")
                    print(f"Full response output: {json.dumps(response.get('output', {}), default=str)[:2000]}")
                    raise

            except Exception as converse_err:
                print(f"Converse API failed: {converse_err}, trying invoke_model")

                # Fallback: invoke_model with OpenAI-compatible format
                request_body = json.dumps({
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                    'max_tokens': 8192,
                    'temperature': 0,
                })

                response = bedrock_client.invoke_model(
                    modelId=BEDROCK_MODEL_ID,
                    contentType='application/json',
                    accept='application/json',
                    body=request_body,
                )

                response_body = json.loads(response['body'].read())
                print(f"invoke_model response keys: {list(response_body.keys())}")

                if 'choices' in response_body:
                    fixed_xml = response_body['choices'][0]['message']['content'].strip()
                elif 'content' in response_body:
                    if isinstance(response_body['content'], list):
                        fixed_xml = response_body['content'][0].get('text', str(response_body['content'][0])).strip()
                    else:
                        fixed_xml = str(response_body['content']).strip()
                elif 'output' in response_body:
                    fixed_xml = str(response_body['output']).strip()
                elif 'completion' in response_body:
                    fixed_xml = response_body['completion'].strip()
                else:
                    print(f"Unknown response format: {json.dumps(response_body)[:500]}")
                    raise ValueError(f"Unexpected response format. Keys: {list(response_body.keys())}")

            if not fixed_xml:
                raise ValueError("Bedrock returned empty response")

            # Clean the model response to extract only MusicXML
            import re
            
            print(f"Raw response length: {len(fixed_xml)}")
            print(f"Raw response first 200 chars: {fixed_xml[:200]}")
            
            # Strip markdown fences if the model wraps them
            fixed_xml = re.sub(r'```(?:xml|musicxml)?\s*\n?', '', fixed_xml)
            fixed_xml = fixed_xml.replace('```', '').strip()
            
            # Remove reasoning/thinking/scratchpad blocks (model chain-of-thought)
            # These may contain XML-like fragments so we must strip them first
            for tag in ['reasoning', 'think', 'thinking', 'scratchpad']:
                fixed_xml = re.sub(
                    rf'<{tag}\b[^>]*>.*?</{tag}>',
                    '', fixed_xml, flags=re.DOTALL
                )
            fixed_xml = fixed_xml.strip()
            
            # Extract only the XML content starting from <?xml or <score-partwise
            xml_match = re.search(r'(<\?xml\b.*)', fixed_xml, flags=re.DOTALL)
            if not xml_match:
                xml_match = re.search(r'(<score-partwise\b.*)', fixed_xml, flags=re.DOTALL)
            
            if xml_match:
                fixed_xml = xml_match.group(1).strip()
                # Ensure we don't have trailing garbage after </score-partwise>
                end_match = re.search(r'(</score-partwise>)', fixed_xml)
                if end_match:
                    fixed_xml = fixed_xml[:end_match.end()]
            else:
                print(f"Could not find XML in cleaned response: {fixed_xml[:500]}")
                raise ValueError("AI response did not contain valid MusicXML")

            # Fix common AI MusicXML issues
            # AI sometimes writes <step>A#</step> instead of <step>A</step><alter>1</alter>
            fixed_xml = re.sub(
                r'<step>([A-G])#</step>',
                r'<step>\1</step><alter>1</alter>',
                fixed_xml
            )
            fixed_xml = re.sub(
                r'<step>([A-G])b</step>',
                r'<step>\1</step><alter>-1</alter>',
                fixed_xml
            )

            # Remove Guitar Pro processing instructions (<?GP ...?>) that can
            # trigger buggy GP-specific rendering paths in AlphaTab
            fixed_xml = re.sub(r'<\?GP\b.*?\?>', '', fixed_xml, flags=re.DOTALL)

            # Fix grace note structure: <grace/> must come before <pitch>,
            # grace notes must not have <duration>, and slides on grace notes
            # can crash AlphaTab's rendering engine
            def fix_grace_note(m):
                inner = m.group(1)
                grace_match = re.search(r'<grace\s*/?>', inner)
                if not grace_match:
                    return m.group(0)
                # Remove grace element from current position
                fixed = re.sub(r'<grace\s*/?>', '', inner, count=1)
                # Remove <duration>...</duration> from grace notes
                fixed = re.sub(r'<duration>[^<]*</duration>', '', fixed, count=1)
                # Remove slide notations from grace notes
                fixed = re.sub(r'<slide\b[^/]*/>', '', fixed)
                # Insert <grace /> as first child
                return f'<note><grace />{fixed}</note>'
            fixed_xml = re.sub(
                r'<note>(.*?)</note>',
                fix_grace_note,
                fixed_xml,
                flags=re.DOTALL
            )

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
