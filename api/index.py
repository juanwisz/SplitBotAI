import json
from src.calculator.gpt_math_calculator import GroupExpenseCalculator

# Initialize the calculator
calculator = GroupExpenseCalculator()

# Vercel expects a `handler` function as the entry point
def handler(request):
    # Parse the request body
    try:
        content_length = int(request.headers.get("content-length", 0))
        request_body = request.body.read(content_length)
        data = json.loads(request_body)
    except Exception:
        return {
            "statusCode": 400,
            "body": json.dumps({"status": "error", "message": "Invalid JSON body"})
        }

    # Route based on the path
    if request.path == "/api/add-transactions":
        try:
            # Add transactions to the calculator
            calculator.add_transactions(data["transactions"])
            response = {"status": "success", "message": "Transactions added"}
            return {
                "statusCode": 200,
                "body": json.dumps(response)
            }
        except Exception as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": str(e)})
            }

    elif request.path == "/api/calculate":
        try:
            # Calculate balances
            balances = calculator.calculate_balances()
            response = {"status": "success", "balances": balances}
            return {
                "statusCode": 200,
                "body": json.dumps(response)
            }
        except Exception as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": str(e)})
            }

    else:
        # Return 404 for invalid endpoints
        return {
            "statusCode": 404,
            "body": json.dumps({"status": "error", "message": "Invalid endpoint"})
        }

