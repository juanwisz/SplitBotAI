# src/python/server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
from calculator.gpt_expense_calculator import GroupExpenseCalculator, GPTExpenseChat
from openai import OpenAI
import json
import os

# Initialize OpenAI client and core components once
openai_client = OpenAI(api_key='api-key-here')
calculator = GroupExpenseCalculator()  # Will be a singleton
chat = GPTExpenseChat(openai_client, calculator)  # Will be a singleton

class ExpenseHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            # Process the query using the existing chat instance
            result = chat.interact(data["query"])

            # Send response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            print(f"Error processing request: {str(e)}")  # Debug logging
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode())

def run_server(port=3001):
    server_address = ("", port)
    httpd = HTTPServer(server_address, ExpenseHandler)
    print(f"Server running on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(3001)
    print(f"Starting server on port {port}...")
    run_server(port)
