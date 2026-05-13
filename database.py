import sqlite3
import json

def obter_conexao():
    conexao = sqlite3.connect('ecos_database.db', check_same_thread=False)
    conexao.row_factory = sqlite3.Row 
    return conexao

# ==========================================
# FUNÇÕES DE LEITURA (READ)
# ==========================================

def listar_motoristas_ativos():
    conexao = obter_conexao()
    cursor = conexao.cursor()
    cursor.execute("SELECT id, nome, matricula FROM dim_motorista WHERE status = 'ATIVO' ORDER BY nome")
    motoristas = cursor.fetchall()
    conexao.close()
    return [{"id": m["id"], "nome": m["nome"], "matricula": m["matricula"]} for m in motoristas]

def listar_veiculos_ativos():
    conexao = obter_conexao()
    cursor = conexao.cursor()
    # Agora puxamos TODOS os campos para poder jogar de volta na tela quando formos editar
    cursor.execute("SELECT * FROM dim_veiculo WHERE status = 'ATIVO' ORDER BY placa")
    veiculos = cursor.fetchall()
    conexao.close()
    
    return [{
        "id": v["id"], 
        "placa": v["placa"], 
        "modelo": v["marca_modelo"],
        "ano": v["ano_modelo"],
        "combustivel": v["tipo_combustivel"],
        "especie": v["especie_capacidade"],
        "proprietario": v["proprietario_locadora"]
    } for v in veiculos]

# ==========================================
# FUNÇÕES DE CRIAÇÃO (CREATE)
# ==========================================

def salvar_motorista(nome, matricula):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute("INSERT INTO dim_motorista (nome, matricula) VALUES (?, ?)", (nome, matricula))
        conexao.commit()
        return True, "Motorista cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Erro: Essa matrícula já está cadastrada no sistema."
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"
    finally:
        conexao.close()

def salvar_veiculo(placa, modelo, ano, combustivel, especie, proprietario):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute('''
            INSERT INTO dim_veiculo 
            (placa, marca_modelo, ano_modelo, tipo_combustivel, especie_capacidade, proprietario_locadora) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (placa, modelo, ano, combustivel, especie, proprietario))
        conexao.commit()
        return True, "Veículo cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Erro: Essa placa já está cadastrada no sistema."
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"
    finally:
        conexao.close()

# ==========================================
# FUNÇÕES DE ATUALIZAÇÃO E EXCLUSÃO (UPDATE / DELETE)
# ==========================================

def editar_motorista(id_motorista, nome, matricula):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute("UPDATE dim_motorista SET nome = ?, matricula = ? WHERE id = ?", (nome, matricula, id_motorista))
        conexao.commit()
        return True, "Motorista atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro ao editar: {str(e)}"
    finally:
        conexao.close()

def excluir_motorista(id_motorista):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM dim_motorista WHERE id = ?", (id_motorista,))
        conexao.commit()
        return True, "Motorista excluído com sucesso!"
    except sqlite3.IntegrityError:
        # Proteção do Banco: Se ele já tem viagens salvas, o banco não deixa apagar para não quebrar o B.I.
        return False, "Este motorista possui viagens no sistema e não pode ser excluído (apenas inativado no futuro)."
    finally:
        conexao.close()

def editar_veiculo(id_veiculo, placa, modelo, ano, combustivel, especie, proprietario):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute('''
            UPDATE dim_veiculo 
            SET placa = ?, marca_modelo = ?, ano_modelo = ?, tipo_combustivel = ?, especie_capacidade = ?, proprietario_locadora = ?
            WHERE id = ?
        ''', (placa, modelo, ano, combustivel, especie, proprietario, id_veiculo))
        conexao.commit()
        return True, "Veículo atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro ao editar: {str(e)}"
    finally:
        conexao.close()

def excluir_veiculo(id_veiculo):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM dim_veiculo WHERE id = ?", (id_veiculo,))
        conexao.commit()
        return True, "Veículo excluído com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Este veículo possui viagens no sistema e não pode ser excluído."
    finally:
        conexao.close()


# ==========================================
# FUNÇÕES DE FATO (Salvando o BDT auditado)
# ==========================================

def salvar_jornada(id_motorista, id_veiculo, viagens, alertas):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        # Transformamos a lista de alertas em um texto para ficar guardado como log da viagem
        alertas_str = json.dumps(alertas, ensure_ascii=False) if alertas else "Nenhum alerta"
        
        for v in viagens:
            # Garantindo que os números são floats para não dar erro matemático no banco
            km_in = float(v['km_in'])
            km_out = float(v['km_out'])
            distancia = km_out - km_in
            
            cursor.execute('''
                INSERT INTO fato_viagem 
                (id_motorista, id_veiculo, data_viagem, hora_inicio, hora_fim, origem, destino, km_inicial, km_final, distancia_percorrida, km_maps_opcional, alertas_gerados) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                id_motorista, 
                id_veiculo, 
                v['dia'], 
                v['hora_in'], 
                v['hora_out'], 
                v['origem'], 
                v['destino'], 
                km_in, 
                km_out, 
                distancia, 
                v.get('km_maps', ''), 
                alertas_str
            ))
            
        conexao.commit()
        return True, "Jornada salva com sucesso no Banco de Dados!"
    except Exception as e:
        conexao.rollback() # Se der erro no meio, ele desfaz tudo para não corromper o banco
        return False, f"Erro ao salvar jornada: {str(e)}"
    finally:
        conexao.close()