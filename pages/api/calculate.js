# src/python/server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
from calculator.gpt_expense_calculator import GroupExpenseCalculator, GPTExpenseChat
from openai import OpenAI
import json
import os

class ExpenseHandler(BaseHTTPRequestHandler):
    # Class-level variables to maintain state
    calculator = GroupExpenseCalculator()
    chat = None
    openai_client = None

    def do_POST(self):
        try:
            # Initialize OpenAI client and chat if not already done
            if not self.openai_client:
                self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.chat = GPTExpenseChat(self.openai_client, self.calculator)

            # Read request body
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            # Process the query
            result = self.chat.interact(data["query"])

            # Send response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode())

    def log_message(self, format, *args):
        # Override to customize logging
        print(f"Server Log: {format%args}")

def run_server(port=3001):
    server_address = ("", port)
    httpd = HTTPServer(server_address, ExpenseHandler)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(os.getenv("PYTHON_SERVER_PORT", 3001))
    run_server(port)
