import os
import json
import uuid
import boto3
from typing import Any, Dict

s3_client = boto3.client("s3")
ecs_client = boto3.client("ecs")

# Fargate configuration from environment variables
ECS_CLUSTER = os.environ.get("ECS_CLUSTER", "eg-solo-inference-cluster")
ECS_TASK_DEFINITION = os.environ.get("ECS_TASK_DEFINITION", "eg-solo-inference-task")
ECS_SUBNETS = os.environ.get("ECS_SUBNETS", "").split(",")
ECS_SECURITY_GROUPS = os.environ.get("ECS_SECURITY_GROUPS", "").split(",")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "solola-bucket")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler that triggers a Fargate task for ML inference.
    
    Event: { "audio_key": "uploads/song.wav", "bucket": "my-bucket", "user_id": "user-123" }
    
    Returns: { "task_id": "...", "status": "PENDING" }
    """
    bucket = event.get("bucket", S3_BUCKET)
    audio_key = event.get("audio_key")
    user_id = event.get("user_id", "anonymous")  # Accept userId from API Lambda
    
    if not audio_key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'audio_key' in request"})
        }
    
    print(f"Starting inference - Audio: {audio_key}, User: {user_id}")
    print(f"[DEBUG] user_id type: {type(user_id)}, value: '{user_id}'")
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Validate that the audio file exists in S3
    try:
        s3_client.head_object(Bucket=bucket, Key=audio_key)
    except Exception as e:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Audio file not found: {audio_key}", "details": str(e)})
        }
    
    # Filter out empty strings from subnet/security group lists
    subnets = [s.strip() for s in ECS_SUBNETS if s.strip()]
    security_groups = [s.strip() for s in ECS_SECURITY_GROUPS if s.strip()]
    
    if not subnets:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "No ECS subnets configured. Set ECS_SUBNETS env var."})
        }
    
    # Start Fargate task
    try:
        print(f"[DEBUG] About to start ECS task with USER_ID: '{user_id}'")
        print(f"[DEBUG] Environment overrides: BUCKET={bucket}, AUDIO_KEY={audio_key}, TASK_ID={task_id}, USER_ID={user_id}")
        
        response = ecs_client.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=ECS_TASK_DEFINITION,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": "ENABLED"
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": "inference",
                        "environment": [
                            {"name": "BUCKET", "value": bucket},
                            {"name": "AUDIO_KEY", "value": audio_key},
                            {"name": "TASK_ID", "value": task_id},
                            {"name": "USER_ID", "value": user_id},  # Pass userId to ECS task
                        ]
                    }
                ]
            },
            tags=[
                {"key": "TaskId", "value": task_id},
                {"key": "AudioKey", "value": audio_key},
                {"key": "UserId", "value": user_id},  # Tag task with userId
            ]
        )
        
        ecs_task_arn = response["tasks"][0]["taskArn"] if response.get("tasks") else None
        
        if not ecs_task_arn:
            failures = response.get("failures", [])
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Failed to start Fargate task",
                    "failures": failures
                })
            }
        
        return {
            "statusCode": 202,
            "body": json.dumps({
                "status": "PENDING",
                "task_id": task_id,
                "ecs_task_arn": ecs_task_arn,
                "user_id": user_id,  # Include userId in response
                "message": "Inference task started. Poll for results.",
                "result_location": f"s3://{bucket}/inference_results/{task_id}/"
            })
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to start Fargate task: {str(e)}"})
        }


def check_status_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Check the status of a Fargate inference task.
    
    Event: { "task_id": "...", "bucket": "..." }
    """
    task_id = event.get("task_id")
    bucket = event.get("bucket", S3_BUCKET)
    
    if not task_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing task_id"})}
    
    # Check if result file exists in S3
    try:
        result_prefix = f"inference_results/{task_id}/"
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=result_prefix)
        
        result_files = [obj["Key"] for obj in response.get("Contents", [])]
        result_json = [f for f in result_files if f.endswith("_result.json")]
        
        if result_json:
            # Task completed - fetch result
            result_obj = s3_client.get_object(Bucket=bucket, Key=result_json[0])
            result_data = json.loads(result_obj["Body"].read().decode("utf-8"))
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "COMPLETED",
                    "task_id": task_id,
                    "result": result_data
                })
            }
    except Exception:
        pass
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "PENDING",
            "task_id": task_id,
            "message": "Task is still running or result not yet available"
        })
    }
