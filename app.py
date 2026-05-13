# arquivo: app.py
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from services.auditoria import rodar_auditoria_completa
import fitz
import re
import io
from database import (
    listar_motoristas_ativos, listar_veiculos_ativos, 
    salvar_motorista, salvar_veiculo,
    editar_motorista, excluir_motorista,
    editar_veiculo, excluir_veiculo,
    salvar_jornada
)


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/cadastros', methods=['GET'])
def obter_cadastros():
    motoristas = listar_motoristas_ativos()
    veiculos = listar_veiculos_ativos()
    
    return jsonify({
        "motoristas": motoristas,
        "veiculos": veiculos
    })

@app.route('/api/motoristas/salvar', methods=['POST'])
def api_salvar_motorista():
    dados = request.get_json()
    nome = dados.get('nome')
    matricula = dados.get('matricula')
    
    sucesso, mensagem = salvar_motorista(nome, matricula)
    
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    else:
        return jsonify({"status": "erro", "mensagem": mensagem}), 400

@app.route('/api/veiculos/salvar', methods=['POST'])
def api_salvar_veiculo():
    dados = request.get_json()
    sucesso, mensagem = salvar_veiculo(
        dados.get('placa'), 
        dados.get('modelo'), 
        dados.get('ano'), 
        dados.get('combustivel'), 
        dados.get('especie'), 
        dados.get('proprietario')
    )
    
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    else:
        return jsonify({"status": "erro", "mensagem": mensagem}), 400
    
# --- ROTAS DE CRUD: MOTORISTAS ---

@app.route('/api/motoristas/excluir/<int:id_motorista>', methods=['DELETE'])
def api_excluir_motorista(id_motorista):
    sucesso, mensagem = excluir_motorista(id_motorista)
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    return jsonify({"status": "erro", "mensagem": mensagem}), 400

@app.route('/api/motoristas/editar/<int:id_motorista>', methods=['PUT'])
def api_editar_motorista(id_motorista):
    dados = request.get_json()
    sucesso, mensagem = editar_motorista(id_motorista, dados.get('nome'), dados.get('matricula'))
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    return jsonify({"status": "erro", "mensagem": mensagem}), 400

# --- ROTAS DE CRUD: VEÍCULOS ---

@app.route('/api/veiculos/excluir/<int:id_veiculo>', methods=['DELETE'])
def api_excluir_veiculo(id_veiculo):
    sucesso, mensagem = excluir_veiculo(id_veiculo)
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    return jsonify({"status": "erro", "mensagem": mensagem}), 400

@app.route('/api/veiculos/editar/<int:id_veiculo>', methods=['PUT'])
def api_editar_veiculo(id_veiculo):
    dados = request.get_json()
    sucesso, mensagem = editar_veiculo(
        id_veiculo, dados.get('placa'), dados.get('modelo'), 
        dados.get('ano'), dados.get('combustivel'), 
        dados.get('especie'), dados.get('proprietario')
    )
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    return jsonify({"status": "erro", "mensagem": mensagem}), 400

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
        # ATUALIZAÇÃO: Usar BytesIO e ExcelFile para ler várias abas de forma segura
        file_bytes = file.read()
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        
        df_bdt = pd.read_excel(xls, sheet_name='BDT Validado')
        df_bdt = df_bdt.dropna(subset=['Dia'])
        
        df_comb = pd.DataFrame()
        # Valida se a aba existe para evitar erros
        if 'Abastecimentos' in xls.sheet_names:
            df_comb = pd.read_excel(xls, sheet_name='Abastecimentos')
            # Busca pela coluna "dia" independente de estar maiúscula ou minúscula
            col_dia = 'Dia' if 'Dia' in df_comb.columns else 'dia'
            if col_dia in df_comb.columns:
                df_comb = df_comb.dropna(subset=[col_dia])

        # Formatação para não aparecer "nan" na tela do HTML
        def safe_str(val):
            if pd.isna(val): return ""
            if isinstance(val, float) and val.is_integer(): return str(int(val))
            return str(val).strip()

        bdt_list = []
        for _, row in df_bdt.iterrows():
            bdt_list.append({
                "dia": str(int(row["Dia"])),
                "hora_in": safe_str(row.get("Hora In", "")),
                "hora_out": safe_str(row.get("Hora Fim", "")),
                "origem": safe_str(row["Origem"]),
                "destino": safe_str(row["Destino"]),
                "km_in": safe_str(row["KM Inicial"]),
                "km_out": safe_str(row["KM Final"])
            })
        
        comb_list = []
        if not df_comb.empty:
            for _, row in df_comb.iterrows():
                col_dia = row.get("Dia") or row.get("dia")
                col_hora = row.get("Hora") or row.get("hora") or ""
                col_km = row.get("KM Marcado na Bomba") or row.get("km_bomba") or row.get("KM_Abastecimento")
                col_litros = row.get("Litros Abastecidos") or row.get("litros")

                comb_list.append({
                    "dia": str(int(col_dia)) if pd.notna(col_dia) else "",
                    "hora": safe_str(col_hora),
                    "km_bomba": safe_str(col_km),
                    "litros": safe_str(col_litros)
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
        file_bytes = file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        texto_completo = ""
        for page in doc:
            texto_completo += page.get_text("text")

        # 1. Âncora de Data e Hora: Busca o Código de Transação (10 dígitos), seguido de data, seguido de hora.
        # Padrão capturado: "1053719408 04/02/2026 14:51:08" -> Extrai ('04', '14:51')
        matches_data_hora = re.findall(r'\b\d{10}\s+(\d{2})/\d{2}/\d{4}\s+(\d{2}:\d{2}):\d{2}\b', texto_completo)
        
        # 2. Âncora de KM e Litros: Busca a sequência exata de KM, Litros e Valor
        # Padrão capturado: "85013 25.85 160,00" -> Extrai ('85013', '25.85')
        dados_bomba = re.findall(r'\b(\d{5,7})\s+(\d+[\., :]\d{2})\s+\d+[\., :]\d{2}\b', texto_completo)

        comb_list = []
        
        # Se encontrou os pares na mesma quantidade, junta tudo!
        if len(matches_data_hora) > 0 and len(matches_data_hora) == len(dados_bomba):
            for (dia_str, hora_str), (km, litros_raw) in zip(matches_data_hora, dados_bomba):
                
                dia_limpo = str(int(dia_str))
                litros_limpo = litros_raw.replace(',', '.').replace(' ', '.').replace(':', '.')
                
                comb_list.append({
                    "dia": dia_limpo,
                    "hora": hora_str,
                    "km_bomba": km,
                    "litros": litros_limpo
                })
            
            # --- NOVIDADE: DEBUG NO TERMINAL ---
            print("\n" + "="*40)
            print("🚀 DEBUG: LEITURA DO PDF COMBUSTÍVEL")
            print("="*40)
            for i, item in enumerate(comb_list):
                print(f"Item {i+1}: Dia {item['dia']} | Hora: {item['hora']} | KM: {item['km_bomba']} | Litros: {item['litros']}")
            print("="*40 + "\n")
            # -----------------------------------

            return jsonify({"status": "sucesso", "combustivel": comb_list})
        else:
            # DEBUG DE ERRO NO TERMINAL
            print(f"\n❌ ERRO DE DEBUG: Achou {len(matches_data_hora)} datas/horas e {len(dados_bomba)} abastecimentos.")
            erro_msg = f"Falha de pareamento: Encontrou {len(matches_data_hora)} registros de tempo e {len(dados_bomba)} de bomba."
            return jsonify({"status": "erro", "mensagem": erro_msg}), 400

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    
@app.route('/api/gerar_pdf', methods=['POST'])
def api_gerar_pdf():
    dados = request.json
    
    # 1. MONTANDO O HTML (O design será o mesmo para ambas as ferramentas)
    html_template = f"""
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm; background-color: #ffffff; }}
            body {{ font-family: 'Helvetica', sans-serif; color: #333; }}
            .header {{ background-color: #0056b3; color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 5px 0 0 0; font-size: 14px; }}
            table.metrics {{ width: 100%; margin-top: 20px; border-collapse: separate; border-spacing: 10px; }}
            .metric-box {{ background-color: #f8f9fa; border: 1px solid #ddd; padding: 15px; text-align: center; }}
            .metric-value {{ font-size: 18pt; font-weight: bold; color: #0056b3; }}
            .metric-label {{ font-size: 9pt; color: #666; }}
            .alert-group {{ margin-top: 20px; border: 1px solid #ddd; }}
            .alert-header {{ padding: 10px; font-weight: bold; color: white; background-color: #666; }}
            .alert-body {{ padding: 15px; font-size: 10pt; background-color: #fff; }}
            .alert-item {{ margin-bottom: 5px; }}
            .recomendacao {{ background-color: #f8f9fa; padding: 10px; border-left: 3px solid #ccc; margin-top: 10px; font-style: italic; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Relatório de Auditoria de Frota</h1>
            <p>ECOS - Sistema de Controle e Integridade</p>
        </div>

        <table class="metrics">
            <tr>
                <td class="metric-box">
                    <span class="metric-label">KM Declarado</span><br>
                    <span class="metric-value">{dados['km_declarado']}</span>
                </td>
                <td class="metric-box">
                    <span class="metric-label">Não Registrado</span><br>
                    <span class="metric-value" style="color: #dc3545;">{dados['km_salto']}</span>
                </td>
                <td class="metric-box">
                    <span class="metric-label">Total Rodado</span><br>
                    <span class="metric-value" style="color: #28a745;">{dados['km_total']}</span>
                </td>
            </tr>
            <tr>
                <td class="metric-box">
                    <span class="metric-label">Velocidade Média</span><br>
                    <span class="metric-value">{dados['vel_media']}</span>
                </td>
                <td class="metric-box">
                    <span class="metric-label">Consumo Real</span><br>
                    <span class="metric-value">{dados['consumo']}</span>
                </td>
            </tr>
        </table>

        <h2 style="color: #0056b3; border-bottom: 2px solid #0056b3; margin-top: 30px; padding-bottom: 5px;">Alertas e Inconsistências</h2>
    """

    for alerta in dados.get('alertas', []):
        cor_header = "#ffc107" # Amarelo (ALT)
        cor_texto_header = "#333"
        if "🔴" in alerta['titulo']: 
            cor_header = "#dc3545" # Vermelho (ERR)
            cor_texto_header = "white"
        if "🚨" in alerta['titulo']: 
            cor_header = "#8b0000" # Vinho (INC)
            cor_texto_header = "white"

        ocorrencias_html = "".join([f"<li class='alert-item'>{oc}</li>" for oc in alerta['ocorrencias']])
        
        # O xhtml2pdf se dá melhor com <p> do que com <div> dentro de tabelas
        html_template += f"""
        <table class="alert-group" style="width: 100%; margin-bottom: 15px; border-collapse: collapse;">
            <tr>
                <td class="alert-header" style="background-color: {cor_header}; color: {cor_texto_header};">
                    {alerta['titulo']}
                </td>
            </tr>
            <tr>
                <td class="alert-body">
                    <ul style="margin-top:0; padding-left: 20px;">{ocorrencias_html}</ul>
                    <p class="recomendacao" style="background-color: #f8f9fa; padding: 10px; border-left: 3px solid #ccc; margin-top: 10px; font-style: italic; margin-bottom: 0;">
                        <strong>Recomendação:</strong> {alerta['detalhe']}
                    </p>
                </td>
            </tr>
        </table>
        """

    html_template += """
        <div style="text-align: center; font-size: 8pt; color: #999; margin-top: 30px;">
            Gerado digitalmente pela Calculadora de Auditoria ECOS
        </div>
    </body>
    </html>
    """

    pdf_io = io.BytesIO()

    # 2. A MÁGICA DO FALLBACK (Tenta WeasyPrint primeiro, cai para xhtml2pdf se falhar)
    try:
        # Importação feita DENTRO do try, pois é aqui que o Windows costuma gritar o erro
        from weasyprint import HTML
        
        print("🟢 TENTANDO GERAR PDF COM: WeasyPrint (Alta Qualidade)")
        HTML(string=html_template).write_pdf(pdf_io)
        gerador_usado = "WeasyPrint"

    except Exception as e:
        # Se cair aqui, é porque a DLL do Windows falhou ou o WeasyPrint não tá instalado direito
        print("🟡 WEASYPRINT FALHOU. Iniciando Fallback de Segurança para xhtml2pdf.")
        print(f"Erro original: {e}")
        
        try:
            from xhtml2pdf import pisa
            
            print("🟢 GERANDO PDF COM: xhtml2pdf (Modo Compatibilidade)")
            
            # Limpa o buffer para garantir que não tem lixo da tentativa falha
            pdf_io = io.BytesIO() 
            pisa_status = pisa.CreatePDF(io.StringIO(html_template), dest=pdf_io)
            
            if pisa_status.err:
                 return jsonify({"status": "erro", "mensagem": "Falha crítica nas duas bibliotecas de PDF."}), 500
                 
            gerador_usado = "xhtml2pdf"

        except ImportError:
            # Se a pessoa também não instalou o xhtml2pdf, aí ferrou.
            return jsonify({"status": "erro", "mensagem": "Bibliotecas de PDF não estão instaladas. Rode 'pip install xhtml2pdf'."}), 500

    pdf_io.seek(0)
    
    print(f"✅ PDF gerado com sucesso usando: {gerador_usado}")

    return send_file(pdf_io, mimetype='application/pdf', as_attachment=True, download_name="Auditoria_ECOS.pdf")

@app.route('/api/viagens/salvar', methods=['POST'])
def api_salvar_viagens():
    dados = request.get_json()
    id_motorista = dados.get('id_motorista')
    id_veiculo = dados.get('id_veiculo')
    viagens = dados.get('bdt', [])
    alertas = dados.get('alertas', []) 
    
    if not viagens:
        return jsonify({"status": "erro", "mensagem": "Nenhuma viagem encontrada para salvar."}), 400
        
    sucesso, mensagem = salvar_jornada(id_motorista, id_veiculo, viagens, alertas)
    
    if sucesso:
        return jsonify({"status": "sucesso", "mensagem": mensagem}), 200
    return jsonify({"status": "erro", "mensagem": mensagem}), 400

if __name__ == '__main__':
    app.run(debug=True)