# arquivo: dbadmin.py
from flask import Flask, render_template_string, jsonify, request
import sqlite3
import os
from services.drive_sync import baixar_banco_mais_recente, enviar_banco_para_o_drive
from dotenv import load_dotenv
load_dotenv()  # <-- Carrega as configurações do arquivo .env local

app = Flask(__name__)
DB_PATH = 'ecos_database.db'

def obter_conexao():
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    return conexao

# Template HTML Admin em String única para rodar em arquivo isolado de utilitário
HTML_ADMIN = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>ECOS - Administrador de Banco de Dados</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: #f4f6f9; color: #333; }
        header { background: #1e293b; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        h1 { margin: 0; font-size: 20px; }
        .container { display: flex; height: calc(100vh - 60px); }
        nav { width: 250px; background: #0f172a; padding: 20px 0; }
        nav button { width: 100%; background: none; border: none; color: #94a3b8; padding: 12px 20px; text-align: left; font-size: 15px; cursor: pointer; transition: 0.2s; }
        nav button:hover, nav button.active { background: #1e293b; color: white; border-left: 4px solid #38bdf8; }
        main { flex: 1; padding: 30px; overflow-y: auto; }
        .table-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
        th, td { border: 1px solid #e2e8f0; padding: 10px; text-align: left; }
        th { background: #f8fafc; font-weight: 600; }
        tr:hover { background: #f1f5f9; }
        .btn { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }
        .btn-edit { background: #eab308; color: white; margin-right: 5px; }
        .btn-del { background: #ef4444; color: white; }
        .btn-add { background: #10b981; color: white; padding: 10px 16px; font-size: 14px; margin-bottom: 15px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }
        .modal-content { background: white; padding: 25px; border-radius: 8px; width: 450px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px; }
        .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    </style>
</head>
<body>
    <header>
        <h1>ECOS Database Management Admin Panel</h1>
        <button onclick="sincronizarNuvem()" style="background:#38bdf8; border:none; padding:8px 15px; border-radius:4px; color:black; font-weight:bold; cursor:pointer;">🔄 Forçar Sync com Drive</button>
    </header>
    <div class="container">
        <nav>
            <button class="active" onclick="mudarTabela(this, 'dim_motorista')">👤 dim_motorista</button>
            <button onclick="mudarTabela(this, 'dim_veiculo')">🚛 dim_veiculo</button>
            <button onclick="mudarTabela(this, 'fato_viagem')">🗺️ fato_viagem</button>
            <button onclick="mudarTabela(this, 'fato_abastecimento')">⛽ fato_abastecimento</button>
        </nav>
        <main>
            <button class="btn btn-add" onclick="abrirModalAdicionar()">➕ Inserir Novo Registro</button>
            <div class="table-container">
                <h2 id="titulo-tabela" style="margin-top:0;">Tabela: dim_motorista</h2>
                <div id="wrapper-tabela"></div>
            </div>
        </main>
    </div>

    <div class="modal" id="formModal">
        <div class="modal-content">
            <h3 id="modal-titulo" style="margin-top:0;">Editar Registro</h3>
            <form id="registroForm">
                <input type="hidden" id="field-id">
                <div id="form-fields-dynamic"></div>
                <div class="modal-actions">
                    <button type="button" class="btn" style="background:#94a3b8; color:white;" onclick="fecharModal()">Cancelar</button>
                    <button type="submit" class="btn" style="background:#10b981; color:white;">Salvar Alterações</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let tabelaAtual = 'dim_motorista';
        let dadosCarregados = [];

        async function carregarTabela() {
            document.getElementById('titulo-tabela').innerText = `Tabela: ${tabelaAtual}`;
            const res = await fetch(`/admin/api/${tabelaAtual}`);
            const json = await res.json();
            dadosCarregados = json.linhas;
            
            if (json.linhas.length === 0) {
                document.getElementById('wrapper-tabela').innerHTML = '<p style="color:#64748b; font-style:italic;">Nenhum registro encontrado nesta tabela.</p>';
                return;
            }

            const colunas = Object.keys(json.linhas[0]);
            let html = '<table><thead><tr>';
            colunas.forEach(col => html += `<th>${col}</th>`);
            html += '<th style="width:120px;">Ações</th></tr></thead><tbody>';

            json.linhas.forEach((linha, idx) => {
                html += '<tr>';
                colunas.forEach(col => html += `<td>${linha[col] !== null ? linha[col] : ''}</td>`);
                html += `<td>
                    <button class="btn btn-edit" onclick="abrirModalEditar(${idx})">📝</button>
                    <button class="btn btn-del" onclick="deletarRegistro(${linha.id})">🗑️</button>
                </td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('wrapper-tabela').innerHTML = html;
        }

        function mudarTabela(btn, tabela) {
            document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            tabelaAtual = tabela;
            carregarTabela();
        }

        function abrirModalAdicionar() {
            document.getElementById('modal-titulo').innerText = `Adicionar em ${tabelaAtual}`;
            document.getElementById('field-id').value = '';
            gerarCamposFormularios({});
            document.getElementById('formModal').style.display = 'flex';
        }

        function abrirModalEditar(index) {
            const row = dadosCarregados[index];
            document.getElementById('modal-titulo').innerText = `Editar em ${tabelaAtual} (ID: ${row.id})`;
            document.getElementById('field-id').value = row.id;
            gerarCamposFormularios(row);
            document.getElementById('formModal').style.display = 'flex';
        }

        function gerarCamposFormularios(dados) {
            const container = document.getElementById('form-fields-dynamic');
            container.innerHTML = '';
            
            // Definição de colunas por tabela para não renderizar ID na mão
            const mapeamento = {
                dim_motorista: ['nome', 'matricula', 'status'],
                dim_veiculo: ['placa', 'marca_modelo', 'ano_modelo', 'tipo_combustivel', 'especie_capacidade', 'proprietario_locadora', 'status'],
                fato_viagem: ['id_motorista', 'id_veiculo', 'data_viagem', 'hora_inicio', 'hora_fim', 'origem', 'destino', 'km_inicial', 'km_final', 'distancia_percorrida', 'km_maps_opcional', 'alertas_gerados'],
                fato_abastecimento: ['id_motorista', 'id_veiculo', 'data_iso', 'hora', 'km_bomba', 'litros']
            };

            mapeamento[tabelaAtual].forEach(campo => {
                const valor = dados[campo] !== undefined ? dados[campo] : '';
                container.innerHTML += `
                    <div class="form-group">
                        <label>${campo.toUpperCase()}</label>
                        <input type="text" name="${campo}" value="${valor}">
                    </div>
                `;
            });
        }

        function fecharModal() { document.getElementById('formModal').style.display = 'none'; }

        document.getElementById('registroForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const payload = { id: document.getElementById('field-id').value };
            formData.forEach((value, key) => payload[key] = value);

            const res = await fetch(`/admin/api/${tabelaAtual}/salvar`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const r = await res.json();
            alert(r.mensagem);
            fecharModal();
            carregarTabela();
        };

        async function deletarRegistro(id) {
            if (!confirm(`Tem certeza absoluta que deseja EXCLUIR o registro ID ${id}?`)) return;
            const res = await fetch(`/admin/api/${tabelaAtual}/excluir/${id}`, { method: 'DELETE' });
            const r = await res.json();
            alert(r.mensagem);
            carregarTabela();
        }

        async function sincronizarNuvem() {
            alert("Sincronizando... Aguarde a confirmação em tela.");
            const res = await fetch('/admin/api/sync', { method: 'POST' });
            const r = await res.json();
            alert(r.mensagem);
        }

        // Carga inicial
        carregarTabela();
    </script>
</body>
</html>
"""

@app.route('/admin')
def painel_admin():
    return render_template_string(HTML_ADMIN)

@app.route('/admin/api/<tabela>', methods=['GET'])
def api_listar_tabela(tabela):
    if tabela not in ['dim_motorista', 'dim_veiculo', 'fato_viagem', 'fato_abastecimento']:
        return jsonify({"erro": "Tabela inválida"}), 400
    conexao = obter_conexao()
    cursor = conexao.cursor()
    cursor.execute(f"SELECT * FROM {tabela} ORDER BY id DESC")
    linhas = [dict(row) for row in cursor.fetchall()]
    conexao.close()
    return jsonify({"linhas": linhas})

@app.route('/admin/api/<tabela>/salvar', methods=['POST'])
def api_salvar_registro(tabela):
    dados = request.get_json()
    id_reg = dados.get('id')
    conexao = obter_conexao()
    cursor = conexao.cursor()
    
    campos = [k for k in dados.keys() if k != 'id']
    valores = [dados[k] for k in campos]
    
    try:
        if id_reg: # UPDATE
            set_clause = ", ".join([f"{c} = ?" for c in campos])
            valores.append(id_reg)
            cursor.execute(f"UPDATE {tabela} SET {set_clause} WHERE id = ?", valores)
            msg = "Registro atualizado com sucesso localmente!"
        else: # INSERT
            colunas_str = ", ".join(campos)
            placeholders = ", ".join(["?" for _ in campos])
            cursor.execute(f"INSERT INTO {tabela} ({colunas_str}) VALUES ({placeholders})", valores)
            msg = "Novo registro inserido com sucesso localmente!"
        
        conexao.commit()
        enviar_banco_para_o_drive() # Força persistência imediata no Google Drive
        return jsonify({"status": "sucesso", "mensagem": msg})
    except Exception as e:
        conexao.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    finally:
        conexao.close()

@app.route('/admin/api/<tabela>/excluir/<int:id_reg>', methods=['DELETE'])
def api_excluir_registro(tabela, id_reg):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute(f"DELETE FROM {tabela} WHERE id = ?", (id_reg,))
        conexao.commit()
        enviar_banco_para_o_drive() # Sincroniza exclusão no drive
        return jsonify({"status": "sucesso", "mensagem": f"ID {id_reg} deletado e sincronizado na Nuvem!"})
    except Exception as e:
        conexao.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    finally:
        conexao.close()

@app.route('/admin/api/sync', methods=['POST'])
def api_forcar_sync():
    sucesso = enviar_banco_para_o_drive()
    if sucesso:
        return jsonify({"mensagem": "Banco enviado para o Drive com sucesso!"})
    return jsonify({"mensagem": "Falha na sincronização. Veja os logs do console."}), 500

if __name__ == '__main__':
    # Inicializa baixando o arquivo mais recente da nuvem antes de abrir o painel local
    print("📥 Puxando estado atual da nuvem para o painel administrativo...")
    baixar_banco_mais_recente()
    app.run(port=5001, debug=True)