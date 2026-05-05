# arquivo: app.py
from flask import Flask, render_template, request, jsonify
import pandas as pd
from services.auditoria import rodar_auditoria_completa

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

if __name__ == '__main__':
    app.run(debug=True)