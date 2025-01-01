# api/index.py
from http.server import BaseHTTPRequestHandler
import json
from src.calculator.gpt_math_calculator import GroupExpenseCalculator

calculator = GroupExpenseCalculator()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        request_body = self.rfile.read(content_length)
        data = json.loads(request_body)
        
        if self.path == '/api/add-transactions':
            try:
                calculator.add_transactions(data['transactions'])
                response = {'status': 'success', 'message': 'Transactions added'}
                self.send_response(200)
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                self.send_response(400)
                
        elif self.path == '/api/calculate':
            try:
                balances = calculator.calculate_balances()
                response = {'status': 'success', 'balances': balances}
                self.send_response(200)
            except Exception as e:
                response = {'status': 'error', 'message': str(e)}
                self.send_response(400)
        else:
            response = {'status': 'error', 'message': 'Invalid endpoint'}
            self.send_response(404)
            
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
