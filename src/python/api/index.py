import sys
import json
from src.python.calculator.gpt_expense_calculator import GroupExpenseCalculator


calculator = GroupExpenseCalculator()

def add_transactions(data):
    calculator.add_transactions(data["transactions"])
    return {"status": "success", "message": "Transactions added"}

def calculate():
    balances = calculator.calculate_balances()
    return {"status": "success", "balances": balances}

if __name__ == "__main__":
    command = sys.argv[1]

    if command == "add-transactions":
        try:
            data = json.loads(sys.argv[2])
            response = add_transactions(data)
            print(json.dumps(response))
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif command == "calculate":
        try:
            response = calculate()
            print(json.dumps(response))
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    else:
        print(json.dumps({"error": "Invalid command"}), file=sys.stderr)
        sys.exit(1)

