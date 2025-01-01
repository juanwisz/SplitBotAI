from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import List, Dict, Set, Union, TypedDict
import warnings

class Transaction(TypedDict):
    payer: str
    amount: Union[Decimal, float, int, str]
    receivers: List[str]

class GroupExpenseCalculator:
    """
    A class to manage group expenses and calculate exact net balances with guaranteed numerical precision.

    This class:
    - Maintains a list of transactions where each transaction details who paid, how much, and who should share the cost.
    - Offers a method to compute the final net balances for each receiver.

    Key Features:
    1. Conservation of Money: Sum of all balances = 0 (within 0.01 precision).
    2. Symmetry: Each receiver's fair share is identical.
    3. Minimal Adjustments: Any residual corrections are applied to minimize the number of modified balances.
    4. High Precision: Uses Decimal arithmetic with 28 significant digits internally.
    5. Financial-grade Rounding: Uses ROUND_HALF_UP for all rounding steps.
    6. Large Amounts: Handles amounts up to 999,999,999,999.99.
    7. Guaranteed Zero-Sum: Final adjustments ensure sum of balances = 0 within negligible residual.

    Typical Usage:
    >>> calc = GroupExpenseCalculator()
    >>> calc.add_transaction(payer="Alice", amount="10.00", receivers=["Alice", "Bob"])
    >>> calc.add_transaction(payer="Bob", amount="20.00", receivers=["Alice", "Bob"])
    >>> balances = calc.calculate_balances()
    >>> balances
    {'Alice': -5.0, 'Bob': 5.0}
    """

    def __init__(self) -> None:
        # Set precision to 28 digits for internal Decimal calculations
        getcontext().prec = 28
        # Internal storage of transactions
        self._transactions: List[Transaction] = []
        # Maximum allowed amount (12 digits before decimal)
        self._MAX_AMOUNT = Decimal('999999999999.99')

    def add_transaction(self, payer: str, amount: Union[Decimal, float, int, str], receivers: List[str], **kwargs) -> None:
        """
        Add a transaction to the calculator.

        Args:
            payer (str): Person who paid
            amount (Union[Decimal, float, int, str]): Amount paid
            receivers (List[str]): List of people who should share the cost
            kwargs: Additional fields to ignore (e.g., 'description')

        Raises:
            ValueError: If the amount is negative, zero, or invalid.
            ValueError: If receivers list is empty.
            ValueError: If the amount exceeds the maximum allowed.
            TypeError: If inputs don't match the expected types.
        """
        # Validate inputs
        if not isinstance(payer, str):
            raise TypeError("Payer must be a string")

        try:
            amt = Decimal(str(amount))
        except (TypeError, ValueError, ArithmeticError) as e:
            raise ValueError(f"Invalid amount: {e}")

        if amt <= 0:
            raise ValueError("Amount must be positive")
        if amt > self._MAX_AMOUNT:
            raise ValueError("Amount exceeds maximum allowed value")

        if not isinstance(receivers, list):
            raise TypeError("receivers must be provided as a list")
        if not receivers:
            raise ValueError("receivers list cannot be empty")
        if not all(isinstance(p, str) for p in receivers):
            raise TypeError("All receivers must be strings")

        # Store the transaction without saving additional fields
        self._transactions.append(Transaction(payer=payer, amount=amt, receivers=receivers))


    def add_transactions(self, transactions: List[Transaction]) -> None:
        """
        Add multiple transactions to the calculator at once.

        Args:
            transactions (List[Transaction]): List of transactions, where each transaction
                is a dict containing 'payer', 'amount', and 'receivers' keys.

        Raises:
            TypeError: If transactions is not a list
            ValueError: If any transaction is invalid (amount, receivers, etc.)

        Example:
            >>> calc = GroupExpenseCalculator()
            >>> transactions = [
            ...     {"payer": "Alice", "amount": "10.00", "receivers": ["Alice", "Bob"]},
            ...     {"payer": "Bob", "amount": "20.00", "receivers": ["Alice", "Bob", "Charlie"]}
            ... ]
            >>> calc.add_transactions(transactions)
        """
        if not isinstance(transactions, list):
            raise TypeError("Transactions must be provided as a list")

        for idx, txn in enumerate(transactions):
            try:
                self.add_transaction(**txn)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Transaction {idx} is invalid: {str(e)}")

    def calculate_balances(self) -> Dict[str, float]:
        """
        Calculate exact net balances for all receivers.

        Returns:
            Dict[str, float]: Mapping of persons to their net balance.
                Positive balance means they are owed money.
                Negative balance means they owe money.
            All receivers will be included in the result, even if they never paid.

        Raises:
            ValueError: If transaction data is inconsistent.
            Warnings: If zero-sum property cannot be perfectly achieved (very rare).
        """
        # net[p] will store each person's net gain/loss across *all* transactions
        net = defaultdict(Decimal)

        # Process each transaction individually
        for idx, txn in enumerate(self._transactions):
            required_keys = {'payer', 'amount', 'receivers'}
            if not all(key in txn for key in required_keys):
                raise ValueError(f"Transaction {idx} missing required keys: {required_keys}")

            payer = txn['payer']
            amount = Decimal(str(txn['amount']))
            receivers_list = txn['receivers']

            # Each receiver in this transaction owes an equal share
            share = amount / Decimal(len(receivers_list))

            # Payer's net increases by the full amount
            net[payer] += amount

            # Each receiver in this transaction owes their share
            for receiver in receivers_list:
                net[receiver] -= share

        # Ensure all receivers appear in final output (even if net=0)
        all_receivers: Set[str] = set(net.keys())
        # Round each person's net to 2 decimal places
        rounded_balances = {
            p: net[p].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            for p in all_receivers
        }

        # Check if there's any residual
        residual = sum(rounded_balances.values())
        if abs(residual) >= Decimal('0.01'):
            # Apply correction to the largest (positive) creditor
            # or if residual < 0, then correct the largest debtor
            if residual > 0:
                # largest creditor
                candidate = max(rounded_balances, key=rounded_balances.get)
                correction = residual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                rounded_balances[candidate] -= correction
            else:
                # largest debtor (most negative) if we have negative residual
                candidate = min(rounded_balances, key=rounded_balances.get)
                correction = residual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                rounded_balances[candidate] -= correction

        # Final check if there's still small residual
        final_sum = sum(rounded_balances.values())
        if abs(final_sum) >= Decimal('0.01'):
            warnings.warn(f"Zero-sum violation detected: {float(final_sum)}")

        # Convert Decimal to float before returning
        return {person: float(value) for person, value in rounded_balances.items()}

import unittest

class TestGroupExpenseCalculator(unittest.TestCase):
    def setUp(self):
        self.calculator = GroupExpenseCalculator()

    def test_add_transaction_valid(self):
        self.calculator.add_transaction("Alice", "10.00", ["Alice", "Bob"])
        self.assertEqual(len(self.calculator._transactions), 1)

    def test_add_transaction_invalid_amount(self):
        with self.assertRaises(ValueError):
            self.calculator.add_transaction("Alice", "-10.00", ["Alice", "Bob"])

    def test_add_transaction_invalid_payer(self):
        with self.assertRaises(TypeError):
            self.calculator.add_transaction(123, "10.00", ["Alice", "Bob"])

    def test_add_transaction_no_receivers(self):
        with self.assertRaises(ValueError):
            self.calculator.add_transaction("Alice", "10.00", [])

    def test_calculate_balances_simple(self):
        self.calculator.add_transaction("Alice", "10.00", ["Alice", "Bob"])
        self.calculator.add_transaction("Bob", "20.00", ["Alice", "Bob"])
        expected_balances = {"Alice": -5.00, "Bob": 5.00}
        balances = self.calculator.calculate_balances()
        self.assertEqual(balances, expected_balances)

    def test_calculate_balances_zero_sum(self):
        self.calculator.add_transaction("Alice", "50.00", ["Alice", "Bob", "Charlie"])
        self.calculator.add_transaction("Bob", "30.00", ["Alice", "Bob", "Charlie"])
        self.calculator.add_transaction("Charlie", "20.00", ["Alice", "Bob", "Charlie"])
        balances = self.calculator.calculate_balances()
        self.assertAlmostEqual(sum(balances.values()), 0.00, places=2)

    def test_calculate_balances_rounding(self):
        self.calculator.add_transaction("Alice", "10.01", ["Alice", "Bob"])
        self.calculator.add_transaction("Bob", "20.02", ["Alice", "Bob"])
        balances = self.calculator.calculate_balances()
        self.assertAlmostEqual(sum(balances.values()), 0.00, places=2)

    def test_calculate_balances_all_owe(self):
        self.calculator.add_transaction("Alice", "100.00", ["Alice", "Bob", "Charlie", "Dave"])
        expected_balances = {
            "Alice": 75.00,
            "Bob": -25.00,
            "Charlie": -25.00,
            "Dave": -25.00,
        }
        balances = self.calculator.calculate_balances()
        self.assertEqual(balances, expected_balances)

    def test_direct_payment_between_users(self):
        # Initial expense split between Alice and Bob
        self.calculator.add_transaction("Alice", "30.00", ["Alice", "Bob"])

        # Bob pays his share to Alice
        self.calculator.add_transaction("Bob", "15.00", ["Alice"])

        # Final balances should show Bob owes nothing
        balances = self.calculator.calculate_balances()
        self.assertAlmostEqual(balances["Bob"], 0.00, places=2)

    def test_complex_payment_sequence(self):
        # 1. Alice pays $30 split three ways
        self.calculator.add_transaction("Alice", "30.00", ["Alice", "Bob", "Charlie"])

        # 2. Bob pays his share ($10) directly to Alice
        self.calculator.add_transaction("Bob", "10.00", ["Alice"])

        balances = self.calculator.calculate_balances()
        self.assertAlmostEqual(balances["Bob"], 0.00, places=2)  # Bob should be settled
        self.assertAlmostEqual(balances["Charlie"], -10.00, places=2)  # Charlie still owes
        self.assertAlmostEqual(balances["Alice"], 10.00, places=2)  # Alice is still owed by Charlie

# Run the tests
unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromTestCase(TestGroupExpenseCalculator))

import openai
import os
import json
from google.colab import userdata
client = openai.OpenAI(api_key=userdata.get('OPENAI_API_KEY'))

# OpenAI function schemas for the expense calculator
EXPENSE_CALCULATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_transactions",
            "description": "Add one or more expense transactions where people paid and others share the costs",
            "parameters": {
                "type": "object",
                "properties": {
                    "transactions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "payer": {
                                    "type": "string",
                                    "description": "Name of the person who paid (e.g., 'Alice')."
                                },
                                "amount": {
                                    "type": "string",
                                    "description": "Amount paid as a string in decimal format (e.g., '10.99')."
                                },
                                "receivers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of people sharing the expense. For transfers, this list includes only the person receiving the payment (e.g., ['Alice'])."
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Optional text providing additional details about the transaction (e.g., 'Lunch at a cafe' or 'Transfer for a shared cab ride')."
                                }
                            },
                            "required": ["payer", "amount", "receivers"]
                        },
                        "examples": [
                            {
                                "payer": "Alice",
                                "amount": "30.00",
                                "receivers": ["Alice", "Bob", "Charlie"],
                                "description": "Alice paid for lunch for herself, Bob, and Charlie."
                            },
                            {
                                "payer": "Bob",
                                "amount": "20.00",
                                "receivers": ["Bob", "Charlie"],
                                "description": "Bob paid for snacks for himself and Charlie."
                            },
                            {
                                "payer": "Charlie",
                                "amount": "15.00",
                                "receivers": ["Alice"],
                                "description": "Transfer: Charlie paid $15 to Alice for a shared ride."
                            }
                        ]
                    }
                },
                "required": ["transactions"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_balances",
            "description": "Calculate the current balances for all receivers. Positive balance means they are owed money, negative means they owe money",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    }
]

# System prompt to guide GPT's interactions
SYSTEM_PROMPT = """You are a helpful expense tracking assistant that helps users manage group expenses and see who owes whom.

For adding expenses:
- Extract all expense details from the user's message
- Package single or multiple expenses into the transactions array
- Include the payer in receivers if they're part of the split
- Use exact decimal amounts (e.g. \"10.50\" not \"10.5\" or \"$10.50\")

For showing balances:
- Explain the current state of debts in natural language
- Positive balances mean money is owed TO that person
- Negative balances mean money is owed BY that person

Examples:
"Alice paid $30 for lunch with Bob and Charlie"
→ One transaction: split between Alice, Bob, Charlie

"Add these expenses from yesterday:
Bob paid $20 for snacks for everyone
Charlie paid $45 for movie tickets for Alice"
→ Two transactions in one array

"What does everyone owe?"
→ Calculate and explain current balances

Transfers:
- Transfers are represented as transactions where the payer is not included in the `receivers` list. For example:
  - "Charlie paid $15 to Alice for a shared ride" becomes:
  ```json
  {
      "payer": "Charlie",
      "amount": "15.00",
      "receivers": ["Alice"],
      "description": "Transfer for a shared cab ride."
  }
  ```

"""

from typing import List, Dict, Any
import json
from openai import OpenAI
from decimal import Decimal
from IPython.display import display, clear_output

def run_expense_chat():
    # Initialize OpenAI client and calculator
    client = openai.OpenAI(api_key=userdata.get('OPENAI_API_KEY'))  # Make sure you've set OPENAI_API_KEY
    calculator = GroupExpenseCalculator()

    # Keep conversation history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def show_conversation():
        """Display the conversation in a clear format"""
        # Removed clear_output(wait=True)
        print("💬 Conversation History:")
        print("-" * 50)
        for message in messages[1:]:  # Skip system message
            if message["role"] == "user":
                print(f"\n👤 You: {message['content']}")
            elif message["role"] == "assistant":
                if message.get("content"):
                    print(f"\n🤖 Assistant: {message['content']}")
            elif message["role"] == "tool":
                print(f"\n🔧 Tool Result: {message['content']}")
            elif message["role"] == "debug":  # New message type
                print(f"\n🔍 Debug: {message['content']}")
        print("\n" + "-" * 50)

    def show_balances():
        """Display current balances in a clear format"""
        balances = calculator.calculate_balances()
        print("\n💰 Current Balances:")
        print("-" * 50)
        for person, amount in balances.items():
            if amount > 0:
                print(f"👉 {person} is owed ${amount:.2f}")
            elif amount < 0:
                print(f"👉 {person} owes ${abs(amount):.2f}")
            else:
                print(f"👉 {person} is settled")
        print("-" * 50)

    print("💬 Welcome to the Expense Tracker! Type 'quit' to exit.")
    print("Examples of what you can say:")
    print("- 'Alice paid $30 for lunch with Bob and Charlie'")
    print("- 'Bob and Charlie each paid $20 for drinks'")
    print("- 'Show me the current balances'")
    print("-" * 50)

    while True:
        try:
            # Get user input
            user_input = input("\n👤 Enter your message: ").strip()
            if user_input.lower() == 'quit':
                print("\n👋 Goodbye!")
                break

            # Add user message to history
            messages.append({"role": "user", "content": user_input})

            # Get GPT's response
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=EXPENSE_CALCULATOR_TOOLS
            )

            # Get the assistant's response and convert to dict for message history
            assistant_message = response.choices[0].message
            messages.append({
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
            })

            # Handle any function calls
            if assistant_message.tool_calls:
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    if function_name == "add_transactions":
                        print("\n🔍 Debug - Transactions to add:")
                        print(json.dumps(function_args, indent=2))
                        calculator.add_transactions(**function_args)
                        balances = calculator.calculate_balances()
                        tool_result = {
                            "status": "Transactions added successfully!",
                            "current_balances": balances
                        }
                        tool_result = json.dumps(tool_result)
                    elif function_name == "calculate_balances":
                        tool_result = calculator.calculate_balances()
                    else:
                        tool_result = f"Unknown function: {function_name}"

                    # Add the function result to messages
                    messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": tool_call.id
                    })

                # Get GPT's final response after function calls
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    tools=EXPENSE_CALCULATOR_TOOLS
                )

                # Add the final response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content
                })

            # Show updated conversation and balances
            show_conversation()
            show_balances()

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("\nPlease try again or type 'quit' to exit.")
            continue

run_expense_chat()

