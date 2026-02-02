import csv
import os
import datetime

# Pricing Constants (Feb 2026 - USD per 1 Million Tokens)
PRICE_FLASH_INPUT = 0.30
PRICE_FLASH_OUTPUT = 2.50
PRICE_PRO_INPUT = 1.25
PRICE_PRO_OUTPUT = 10.00

class AuditLogger:
    def __init__(self, filename="audit_detailed_log.csv"):
        self.filename = filename
        # ADDED: Router_Reasoning column
        self.headers = [
            "Timestamp", "Req_ID", "Requirement_Text",
            "Router_Model", "Router_Input_Tokens", "Router_Output_Tokens", "Router_Cost", "Router_Files", "Router_Reasoning",
            "Auditor_Model", "Auditor_Input_Tokens", "Auditor_Output_Tokens", "Auditor_Cost",
            "Audit_Status", "Audit_Reasoning", "Total_Req_Cost"
        ]
        self._initialize_csv()

    def _initialize_csv(self):
        if not os.path.exists(self.filename):
            with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.headers)

    def calculate_cost(self, model_name, input_tok, output_tok):
        in_m = input_tok / 1_000_000
        out_m = output_tok / 1_000_000
        
        if "flash" in model_name.lower():
            cost = (in_m * PRICE_FLASH_INPUT) + (out_m * PRICE_FLASH_OUTPUT)
        else:
            cost = (in_m * PRICE_PRO_INPUT) + (out_m * PRICE_PRO_OUTPUT)
            
        return cost

    def log_requirement(self, req_id, req_text, router_data, auditor_data):
        r_cost = self.calculate_cost(router_data['model'], router_data['input'], router_data['output'])
        a_cost = self.calculate_cost(auditor_data['model'], auditor_data['input'], auditor_data['output'])
        total_cost = r_cost + a_cost

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ADDED: router_data.get('reasoning', 'N/A')
        row = [
            timestamp,
            req_id,
            req_text,
            router_data['model'],
            router_data['input'],
            router_data['output'],
            f"${r_cost:.6f}",
            router_data['files'],
            router_data.get('reasoning', 'N/A'), 
            auditor_data['model'],
            auditor_data['input'],
            auditor_data['output'],
            f"${a_cost:.6f}",
            auditor_data['status'],
            auditor_data['reasoning'],
            f"${total_cost:.6f}"
        ]

        with open(self.filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)