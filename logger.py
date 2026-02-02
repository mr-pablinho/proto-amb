import csv
import os
import json
import datetime

# Pricing Constants (Feb 2026 - USD per 1 Million Tokens)
PRICE_FLASH_INPUT = 0.30
PRICE_FLASH_OUTPUT = 2.50
PRICE_PRO_INPUT = 1.25
PRICE_PRO_OUTPUT = 10.00

class AuditLogger:
    def __init__(self, output_dir="./logs"):
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Generate Unique Session Timestamp
        self.session_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 2. Define File Paths
        self.file_detailed = os.path.join(output_dir, f"audit_detailed_{self.session_ts}.csv")
        self.file_user = os.path.join(output_dir, f"audit_report_USER_{self.session_ts}.csv")
        self.file_metadata = os.path.join(output_dir, f"run_metadata_{self.session_ts}.json")
        
        # 3. Define Headers
        self.headers_detailed = [
            "Req_ID", "Requirement_Text", "Duration_Seconds",
            "Router_Model", "Router_Input_Tokens", "Router_Output_Tokens", "Router_Cost", "Router_Files", "Router_Reasoning",
            "Auditor_Model", "Auditor_Input_Tokens", "Auditor_Output_Tokens", "Auditor_Cost",
            "Audit_Status", "Audit_Reasoning", "Total_Req_Cost"
        ]
        
        # Simplified headers for the client
        self.headers_user = [
            "Req_ID", "Requirement_Text", "Duration_Seconds",
            "Selected_Files", "Audit_Status", "Audit_Reasoning"
        ]

        self._initialize_csvs()

    def _initialize_csvs(self):
        # Init Detailed Log
        with open(self.file_detailed, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers_detailed)
            
        # Init User Log
        with open(self.file_user, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers_user)

    def log_metadata(self, data: dict):
        """Writes run configuration and stats to a JSON file."""
        with open(self.file_metadata, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def calculate_cost(self, model_name, input_tok, output_tok):
        in_m = input_tok / 1_000_000
        out_m = output_tok / 1_000_000
        
        if "flash" in model_name.lower():
            cost = (in_m * PRICE_FLASH_INPUT) + (out_m * PRICE_FLASH_OUTPUT)
        else:
            cost = (in_m * PRICE_PRO_INPUT) + (out_m * PRICE_PRO_OUTPUT)
        return cost

    def log_requirement(self, req_id, req_text, duration, router_data, auditor_data):
        # Calculate Costs
        r_cost = self.calculate_cost(router_data['model'], router_data['input'], router_data['output'])
        a_cost = self.calculate_cost(auditor_data['model'], auditor_data['input'], auditor_data['output'])
        total_cost = r_cost + a_cost

        # --- ROW FOR DETAILED LOG ---
        row_detailed = [
            req_id,
            req_text,
            f"{duration:.2f}",
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

        # --- ROW FOR USER LOG (Clean) ---
        row_user = [
            req_id,
            req_text,
            f"{duration:.2f}",
            router_data['files'], # Selected Files
            auditor_data['status'],
            auditor_data['reasoning']
        ]

        # Write to Detailed
        with open(self.file_detailed, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row_detailed)

        # Write to User Report
        with open(self.file_user, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row_user)