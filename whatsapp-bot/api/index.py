import json

async def handler(request):
    if request.method == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "✅ Bot is alive!"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            print("Received update:", data)
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "✅ Update received"}),
                "headers": {
                    "Content-Type": "application/json"
                }
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)}),
                "headers": {
                    "Content-Type": "application/json"
                }
            }

    else:
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "Method Not Allowed"}),
            "headers": {
                "Content-Type": "application/json"
            }
        }
