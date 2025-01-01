from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import List, Dict, Union, TypedDict
import openai
import json


# Define transaction structure
class Transaction(TypedDict):
    payer: str
    amount: str  # String format to ensure compatibility with JSON and Decimal
    receivers: List[str]


# Expense Calculator Logic with Singleton Pattern
class GroupExpenseCalculator:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GroupExpenseCalculator, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            getcontext().prec = 28
            self._transactions: List[Transaction] = []
            self._initialized = True

    def add_transactions(self, transactions: List[Transaction]) -> Dict[str, Union[str, Dict]]:
        try:
            for txn in transactions:
                self._validate_transaction(txn)
                self._transactions.append(txn)
            return {"status": "success", "message": "Transactions added successfully."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def calculate_balances(self) -> Dict[str, float]:
        net = defaultdict(Decimal)
        for txn in self._transactions:
            payer = txn['payer']
            amount = Decimal(txn['amount'])
            receivers = txn['receivers']

            share = amount / Decimal(len(receivers))
            net[payer] += amount
            for receiver in receivers:
                net[receiver] -= share

        return {person: float(net[person].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) for person in net}

    def _validate_transaction(self, transaction: Transaction):
        if not isinstance(transaction["payer"], str):
            raise ValueError("Payer must be a string")
        if not isinstance(transaction["amount"], str) or not Decimal(transaction["amount"]):
            raise ValueError("Amount must be a valid string representation of a number")
        if not isinstance(transaction["receivers"], list) or not transaction["receivers"]:
            raise ValueError("Receivers must be a non-empty list of strings")
        if not all(isinstance(receiver, str) for receiver in transaction["receivers"]):
            raise ValueError("All receivers must be strings")

    def get_transactions(self) -> List[Transaction]:
        return self._transactions


class GPTExpenseChat:
    _instance = None
    _initialized = False
    
    def __new__(cls, openai_client=None, calculator=None):
        if cls._instance is None:
            cls._instance = super(GPTExpenseChat, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, openai_client, calculator: GroupExpenseCalculator):
        if not self._initialized:
            self.openai_client = openai_client
            self.calculator = calculator
            self.messages = [
                {"role": "system", "content": "You are a helpful assistant managing group expenses. Use tools to process user queries."}
            ]
            self._initialized = True

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def handle_function_call(self, function_name: str, arguments: dict) -> dict:
        if function_name == "add_transactions":
            return self.calculator.add_transactions(arguments["transactions"])
        elif function_name == "calculate_balances":
            return {"status": "success", "balances": self.calculator.calculate_balances()}
        else:
            return {"status": "error", "message": f"Unknown function: {function_name}"}
        
    def interact(self, user_input: str) -> Dict[str, Union[str, dict]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "add_transactions",
                    "description": "Add one or more transactions to the calculator.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "transactions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "payer": {"type": "string"},
                                        "amount": {"type": "string"},
                                        "receivers": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["payer", "amount", "receivers"]
                                }
                            }
                        },
                        "required": ["transactions"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_balances",
                    "description": "Calculate the current balances for all participants.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                }
            }
        ]

        # Add the user input
        self.messages.append({"role": "user", "content": user_input})

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=self.messages,
                tools=tools
            )

            # Get the assistant's message as an object
            assistant_message = response.choices[0].message
            
            # Convert to dict for message history
            message_dict = {
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in (assistant_message.tool_calls or [])
                ] if assistant_message.tool_calls else None
            }
            self.messages.append(message_dict)

            # Handle any function calls
            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    tool_result = self.handle_function_call(function_name, function_args)
                    
                    # Add the function result to messages
                    self.messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": tool_call.id
                    })

                # Get final response after function calls
                final_response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=self.messages,
                    tools=tools
                )
                
                final_message = final_response.choices[0].message
                self.messages.append({
                    "role": "assistant",
                    "content": final_message.content
                })
                
                return {"status": "success", "reply": final_message.content}

            return {"status": "success", "reply": assistant_message.content}

        except Exception as e:
            error_message = {"status": "error", "message": str(e)}
            self.messages.append({
                "role": "assistant",
                "content": str(error_message)
            })
            return error_message


if __name__ == "__main__":
    import sys
    from openai import OpenAI

    if len(sys.argv) < 2:
        print("Usage: python gpt_expense_calculator.py '<USER_QUERY>'")
        sys.exit(1)

    user_query = sys.argv[1]

    # Initialize OpenAI client
    client = OpenAI(api_key='api-key-here')

    # Create instances (these will be singletons)
    calculator = GroupExpenseCalculator()
    chat = GPTExpenseChat(client, calculator)

    # Process user query
    result = chat.interact(user_query)

    # Output result
    print(json.dumps(result, indent=2))
