const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const {
  DynamoDBDocumentClient,
  PutCommand,
  DeleteCommand,
} = require("@aws-sdk/lib-dynamodb");

const ddbClient = new DynamoDBClient({});
const ddb = DynamoDBDocumentClient.from(ddbClient);
const TABLE_NAME = process.env.TABLE_NAME || "eg-solo-websocket-connections";

exports.handler = async (event) => {
  const { connectionId, routeKey, domainName, stage } = event.requestContext;

  console.log("WebSocket event:", {
    connectionId,
    routeKey,
    queryParams: event.queryStringParameters,
  });

  try {
    switch (routeKey) {
      case "$connect":
        await handleConnect(connectionId, event);
        break;

      case "$disconnect":
        await handleDisconnect(connectionId);
        break;

      case "$default":
        console.log("Default route - message received");
        break;
    }

    return { statusCode: 200 };
  } catch (error) {
    console.error("Error:", error);
    return { statusCode: 500 };
  }
};

async function handleConnect(connectionId, event) {
  console.log("Client connected:", connectionId);

  // Get userId from query parameters
  const userId = event.queryStringParameters?.userId || "anonymous";

  if (userId === "anonymous") {
    console.warn("Connection without userId - still allowing");
  }

  // Store connection in DynamoDB
  await ddb.send(
    new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        connectionId,
        userId,
        connectedAt: new Date().toISOString(),
        ttl: Math.floor(Date.now() / 1000) + 86400, // 24 hours TTL
      },
    }),
  );

  console.log("✅ Connection stored for user:", userId);
}

async function handleDisconnect(connectionId) {
  console.log("Client disconnected:", connectionId);

  // Remove connection from DynamoDB
  await ddb.send(
    new DeleteCommand({
      TableName: TABLE_NAME,
      Key: { connectionId },
    }),
  );

  console.log("✅ Connection removed");
}
