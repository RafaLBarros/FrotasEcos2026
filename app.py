# arquivo: app.py
from flask import Flask, render_template, request, jsonify
import pandas as pd
from services.auditoria import rodar_auditoria_completa
import fitz
import re

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/auditar', methods=['POST'])
def api_auditar():
    dados = request.json
    dados_bdt = dados.get('bdt', [])
    dados_combustivel = dados.get('combustivel', [])
    
    resultado = rodar_auditoria_completa(dados_bdt, dados_combustivel)
    return jsonify(resultado)

# NOVIDADE: Rota para importar o Excel
@app.route('/api/importar', methods=['POST'])
def api_importar():
    if 'file' not in request.files:
        return jsonify({"status": "erro", "mensagem": "Nenhum arquivo enviado"}), 400
    
    file = request.files['file']
    try:
        df_bdt = pd.read_excel(file, sheet_name='BDT Validado')
        df_bdt = df_bdt.dropna(subset=['Dia']) # Remove linhas vazias
        
        try:
            df_comb = pd.read_excel(file, sheet_name='Abastecimentos')
            df_comb = df_comb.dropna(subset=['dia'])
        except:
            df_comb = pd.DataFrame() # Se não tiver aba de abastecimento, cria vazia
        
        bdt_list = []
        for _, row in df_bdt.iterrows():
            bdt_list.append({
                "dia": str(int(row["Dia"])),
                "origem": str(row["Origem"]),
                "destino": str(row["Destino"]),
                "km_in": str(row["KM Inicial"]),
                "km_out": str(row["KM Final"])
            })
        
        comb_list = []
        if not df_comb.empty:
            for _, row in df_comb.iterrows():
                comb_list.append({
                    "dia": str(int(row["dia"])),
                    "km_bomba": str(row["km_bomba"]),
                    "litros": str(row["litros"])
                })

        return jsonify({"status": "sucesso", "bdt": bdt_list, "combustivel": comb_list})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    
@app.route('/api/importar_pdf_combustivel', methods=['POST'])
def api_importar_pdf_combustivel():
    if 'file' not in request.files:
        return jsonify({"status": "erro", "mensagem": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    try:
        # 1. Lê o PDF em formato binário direto da memória
        file_bytes = file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        texto_completo = ""
        for page in doc:
            # get_text("text") extrai exatamente igual ao seu "Copiar e Colar"
            texto_completo += page.get_text("text")

        # 2. Pesca as Datas: Procura 10 dígitos, um espaço e a Data (Ex: 1053709242 04/02/2026)
        # O grupo (\\d{2}) captura apenas os dois dígitos do dia!
        datas_encontradas = re.findall(r'\d{10}\s+(\d{2})/\d{2}/\d{4}', texto_completo)

        # 3. Pesca o Abastecimento: Procura a sequência exata de KM, Litros e Valor
        # Ex: 562976 47.83 320,00 -> Ele captura o KM e os Litros.
        dados_bomba = re.findall(r'\b(\d{4,7})\s+(\d+\.\d{2})\s+\d+,\d{2}\b', texto_completo)

        comb_list = []
        
        # 4. Cruza os dados: Se achou 7 datas e 7 abastecimentos, eles formam os pares perfeitos!
        if len(datas_encontradas) > 0 and len(datas_encontradas) == len(dados_bomba):
            # O zip une a primeira data com o primeiro abastecimento, e assim por diante
            for dia_str, (km, litros) in zip(datas_encontradas, dados_bomba):
                dia_limpo = str(int(dia_str)) # Remove o zero da esquerda (ex: "04" vira "4")
                
                comb_list.append({
                    "dia": dia_limpo,
                    "km_bomba": km,
                    "litros": litros
                })
                
            return jsonify({"status": "sucesso", "combustivel": comb_list})
        else:
            return jsonify({
                "status": "erro", 
                "mensagem": f"O sistema encontrou {len(datas_encontradas)} datas e {len(dados_bomba)} abastecimentos e não conseguiu parear. O layout do PDF pode ter mudado."
            }), 400

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)