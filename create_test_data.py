import os
import json
from fpdf import FPDF

# Ensure directories exist
os.makedirs("./data/proyecto_eia", exist_ok=True)
os.makedirs("./data/leyes", exist_ok=True)

def create_pdf(filename, title, content_sections):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=title, ln=1, align='C')
    pdf.ln(10)
    
    for header, text in content_sections.items():
        pdf.set_font("Arial", 'B', size=12)
        pdf.cell(200, 10, txt=header, ln=1, align='L')
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, txt=text)
        pdf.ln(5)
        
    pdf.output(filename)
    print(f"Created {filename}")

# 1. Create Legal Text (Dummy Regulation)
legal_content = {
    "Articulo 45 - Ruido": "El límite máximo permisible de ruido en zona industrial es de 75 decibeles (dB) durante el día. Se requiere monitoreo semestral.",
    "Articulo 80 - Capacitación": "Todo proyecto debe contar con un programa de capacitación social documentado con listas de asistencia.",
    "Articulo 100 - Cierre": "El plan de cierre debe incluir restauración geomorfológica y revegetación."
}
create_pdf("./data/leyes/Reglamento_Ambiental_TULSMA.pdf", "Reglamento Ambiental", legal_content)

# 2. Create Project PDFs (The Test Suite)

# File A: Generic Name, contains specific Plan + Table
file_a_content = {
    "1.4 Plan de Manejo de Desechos": "Los desechos peligrosos serán gestionados por gestor calificado.",
    "2.1 Monitoreo de Ruido": "Se realizó la medición en los puntos N1 y N2. Los resultados se detallan a continuación.",
    "Table 1: Monitoring Capacities": "Punto N1: 72 dB. Punto N2: 74 dB. (Cumple Norma).",
    "Caption": "Table 1 shows noise levels are within limits."
}
create_pdf("./data/proyecto_eia/Chapter_3.pdf", "Capitulo 3: Descripción Técnica", file_a_content)

# File B: Annex, contains Tables required by File A logic
file_b_content = {
    "Annex Q - Data Logs": "Raw data logs for noise monitoring equipment.",
    "Table 2: Monitoring Logs": "Date: 2023-10-01. Calibration: OK. Technician: Juan Perez.",
    "Programa de Capacitacion": "Se realizaron charlas de seguridad el 15 de Octubre."
}
create_pdf("./data/proyecto_eia/Annex_Data.pdf", "Anexos Técnicos", file_b_content)

# File C: Trick File
file_c_content = {
    "Receta de Cocina": "Ingredientes para un ceviche: Pescado, limón, cebolla...",
    "Nota": "Este archivo fue incluido por error administrativo."
}
create_pdf("./data/proyecto_eia/File_Error.pdf", "Archivo Corrupto", file_c_content)

# 3. Create Audit Checklist
checklist = [
    {
        "id": "REQ-001",
        "requirement": "Verificar el cumplimiento de los límites de ruido (75 dB) y evidencia de monitoreo."
    },
    {
        "id": "REQ-002",
        "requirement": "Verificar la existencia del programa de capacitación social."
    },
    {
        "id": "REQ-003",
        "requirement": "Verificar el plan de cierre de minas."
    }
]

with open("./data/audit_checklist.json", "w", encoding='utf-8') as f:
    json.dump(checklist, f, indent=4, ensure_ascii=False)

print("Test Environment Created Successfully.")