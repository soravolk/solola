# WebSocket API Setup

This folder contains the WebSocket API Gateway configuration for real-time communication between clients and the EG Solo backend.

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Client Application                               │
│                                                  │
│  Static Assets (HTML/JS/CSS)                    │
│  ↓                                               │
│  https://cloudfront-domain.com ─────────────────┼──→ CloudFront → S3
│                                                  │
│  WebSocket Connection (Real-time updates)       │
│  ↓                                               │
│  wss://xxx.execute-api.us-east-1.amazonaws.com/│
│      prod ──────────────────────────────────────┼──→ API Gateway WebSocket → Lambda
│                                                  │
└─────────────────────────────────────────────────┘
```

**Key Points:**

- ✅ **Static assets** served via CloudFront + S3
- ✅ **WebSocket connection** goes directly to API Gateway (not through CloudFront)
- ✅ **Separate endpoints** for HTTP and WebSocket traffic

## Files

- `websocket-api.tf` - Terraform configuration for WebSocket API Gateway
- `websocket-client-example.js` - Example client implementation
- `WEBSOCKET_SETUP.md` - This file

## Deployment

### 1. Initialize and Apply Terraform

```bash
cd terraform

# Initialize (if not already done)
terraform init

# Preview changes
terraform plan

# Apply configuration
terraform apply
```

### 2. Get WebSocket URL

After deployment, get your WebSocket URL:

```bash
terraform output websocket_url
```

Output example:

```
wss://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
```

### 3. Update Client Code

Replace the placeholder in your client code with the actual WebSocket URL:

```javascript
const WEBSOCKET_URL = terraform output -raw websocket_url;
const wsClient = new EGSoloWebSocketClient(WEBSOCKET_URL);
```

## Testing the WebSocket

### Using Browser Console

```javascript
// Connect to WebSocket
const ws = new WebSocket(
  "wss://your-api-id.execute-api.us-east-1.amazonaws.com/prod",
);

ws.onopen = () => {
  console.log("Connected!");

  // Send a test message
  ws.send(
    JSON.stringify({
      action: "ping",
      timestamp: Date.now(),
    }),
  );
};

ws.onmessage = (event) => {
  console.log("Received:", event.data);
};

ws.onerror = (error) => {
  console.error("Error:", error);
};

ws.onclose = () => {
  console.log("Disconnected");
};
```

### Using wscat CLI

Install wscat:

```bash
npm install -g wscat
```

Connect and test:

```bash
wscat -c wss://your-api-id.execute-api.us-east-1.amazonaws.com/prod

# After connection, send a message:
{"action": "ping", "data": "hello"}
```

## Lambda Handler

The current Lambda handler is minimal and just accepts connections. It logs:

- Connection events (`$connect`)
- Disconnection events (`$disconnect`)
- Messages (`$default` route)

### Extending the Lambda

To add real functionality, you can:

1. **Store connection IDs** in DynamoDB for broadcast messages
2. **Send messages to clients** using the API Gateway Management API
3. **Integrate with other services** (SQS, SNS, etc.)

Example of sending a message back to the client:

```javascript
const {
  ApiGatewayManagementApiClient,
  PostToConnectionCommand,
} = require("@aws-sdk/client-apigatewaymanagementapi");

const client = new ApiGatewayManagementApiClient({
  endpoint: `https://${domainName}/${stage}`,
});

const command = new PostToConnectionCommand({
  ConnectionId: connectionId,
  Data: JSON.stringify({
    type: "transcription_progress",
    progress: 50,
    message: "Processing audio...",
  }),
});

await client.send(command);
```

## Routes

Currently configured routes:

- `$connect` - Called when client connects
- `$disconnect` - Called when client disconnects
- `$default` - Catches all messages that don't match other routes

### Adding Custom Routes

To add a custom route, modify `websocket-api.tf`:

```hcl
resource "aws_apigatewayv2_route" "custom" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "customAction"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_lambda.id}"
}
```

Then send messages with that action:

```javascript
ws.send(JSON.stringify({ action: 'customAction', data: {...} }));
```

## Monitoring

### CloudWatch Logs

View WebSocket logs:

```bash
# Lambda logs
aws logs tail /aws/lambda/eg-solo-websocket-handler --follow

# API Gateway logs
aws logs tail /aws/apigateway/eg-solo-websocket-api --follow
```

### Metrics

Check API Gateway metrics in CloudWatch:

- Connection count
- Message count
- Error count
- Integration latency

## Cost Considerations

WebSocket API Gateway pricing (as of 2026):

- **Connection minutes**: $0.25 per million connection minutes
- **Messages**: $1.00 per million messages

Example calculation:

- 100 concurrent connections × 60 min/hour × 24 hours = 144,000 connection minutes/day
- Cost: ~$0.036/day or ~$1.08/month for connections
- Plus message costs based on usage

## Troubleshooting

### Connection Fails

1. Check the WebSocket URL is correct
2. Verify the stage is deployed: `terraform apply`
3. Check Lambda permissions in CloudWatch Logs
4. Ensure Lambda has proper IAM permissions

### Messages Not Received

1. Check Lambda logs for errors
2. Verify route key matches the `action` field in your message
3. Test with `$default` route first (catches all messages)

### Can't Send Messages to Clients

1. Ensure Lambda has `execute-api:ManageConnections` permission (already configured)
2. Use correct endpoint format: `https://${domainName}/${stage}`
3. Verify connection ID is still valid

## Clean Up

To destroy WebSocket resources:

```bash
terraform destroy -target=aws_apigatewayv2_api.websocket
```

Or destroy everything:

```bash
terraform destroy
```

## Next Steps

1. **Implement DynamoDB table** to store connection IDs
2. **Add authentication** using Lambda authorizers
3. **Broadcast messages** to multiple clients
4. **Integrate with inference Lambda** to send real-time progress updates
5. **Add error handling** and retry logic

## Resources

- [AWS API Gateway WebSocket API Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html)
- [WebSocket Client API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Terraform AWS Provider - API Gateway v2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apigatewayv2_api)
