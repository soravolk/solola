exports.handler = async (event) => {
  console.log("WebSocket Event:", JSON.stringify(event, null, 2));

  const { routeKey, connectionId } = event.requestContext;

  console.log(`Route: ${routeKey}, ConnectionId: ${connectionId}`);

  // Just accept the connection/message
  return {
    statusCode: 200,
    body: JSON.stringify({ message: "Success" }),
  };
};
