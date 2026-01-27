const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const {
  DynamoDBDocumentClient,
  QueryCommand,
  DeleteCommand,
} = require("@aws-sdk/lib-dynamodb");
const {
  ApiGatewayManagementApiClient,
  PostToConnectionCommand,
} = require("@aws-sdk/client-apigatewaymanagementapi");

const ddbClient = new DynamoDBClient({});
const ddb = DynamoDBDocumentClient.from(ddbClient);

const TABLE_NAME = process.env.TABLE_NAME;
const WEBSOCKET_ENDPOINT = process.env.WEBSOCKET_ENDPOINT;

exports.handler = async (event) => {
  console.log("Notification request:", JSON.stringify(event, null, 2));

  const { userId, type, data } = event;

  if (!userId || userId === "anonymous") {
    console.error("userId is required and cannot be anonymous");
    return { statusCode: 400, body: "userId is required" };
  }

  try {
    // Get all connections for this user
    const result = await ddb.send(
      new QueryCommand({
        TableName: TABLE_NAME,
        IndexName: "UserIdIndex",
        KeyConditionExpression: "userId = :userId",
        ExpressionAttributeValues: {
          ":userId": userId,
        },
      }),
    );

    console.log(
      `Found ${result.Items?.length || 0} connections for user ${userId}`,
    );

    if (!result.Items || result.Items.length === 0) {
      console.log("No active connections found for user");
      return { statusCode: 200, body: "No active connections" };
    }

    const apiGateway = new ApiGatewayManagementApiClient({
      endpoint: WEBSOCKET_ENDPOINT,
    });

    // Send message to all user's connections
    const sendPromises = result.Items.map(async (item) => {
      try {
        await apiGateway.send(
          new PostToConnectionCommand({
            ConnectionId: item.connectionId,
            Data: JSON.stringify({
              type,
              data,
              timestamp: new Date().toISOString(),
            }),
          }),
        );
        console.log(`✅ Sent to connection: ${item.connectionId}`);
        return { connectionId: item.connectionId, status: "sent" };
      } catch (error) {
        console.error(`Error sending to ${item.connectionId}:`, error);

        // If connection is gone (410), remove it from DynamoDB
        if (error.statusCode === 410) {
          console.log(`Removing stale connection: ${item.connectionId}`);
          await ddb.send(
            new DeleteCommand({
              TableName: TABLE_NAME,
              Key: { connectionId: item.connectionId },
            }),
          );
          return { connectionId: item.connectionId, status: "removed" };
        }

        return {
          connectionId: item.connectionId,
          status: "failed",
          error: error.message,
        };
      }
    });

    const results = await Promise.all(sendPromises);

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: "Notifications sent",
        results,
      }),
    };
  } catch (error) {
    console.error("Error:", error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: error.message }),
    };
  }
};
