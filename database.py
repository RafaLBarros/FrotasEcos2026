# arquivo: database.py
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

def salvar_jornada(id_motorista, id_veiculo, viagens, abastecimentos, alertas):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        alertas_str = json.dumps(alertas, ensure_ascii=False) if alertas else "Nenhum alerta"
        
        # ==========================================
        # 1. SALVAR VIAGENS (Com a trava de segurança blindada)
        # ==========================================
        for v in viagens:
            data_v = v['dia']
            hora_in = v['hora_in']
            
            # TRAVA: Pergunta ao banco se essa corrida exata já existe
            cursor.execute('''
                SELECT id_motorista, id_veiculo 
                FROM fato_viagem 
                WHERE data_viagem = ? AND hora_inicio = ? 
                  AND (id_motorista = ? OR id_veiculo = ?)
            ''', (data_v, hora_in, id_motorista, id_veiculo))
            
            conflito = cursor.fetchone()
            
            if conflito:
                conexao.rollback() # Cancela TUDO o que estava sendo feito nesta rodada
                if str(conflito['id_motorista']) == str(id_motorista):
                    return False, f"⚠️ DUPLICATA BLOQUEADA: O motorista já tem uma viagem salva no dia {data_v} exatamente às {hora_in}. Verifique a planilha!"
                else:
                    return False, f"⚠️ CONFLITO DE FROTA: O veículo selecionado já possui viagem salva no dia {data_v} às {hora_in} com OUTRO motorista."
            
            # Se a linha for inédita, prepara para salvar
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
                data_v, 
                hora_in, 
                v['hora_out'], 
                v['origem'], 
                v['destino'], 
                km_in, 
                km_out, 
                distancia, 
                v.get('km_maps', ''), 
                alertas_str
            ))

        # ==========================================
        # 2. SALVAR ABASTECIMENTOS
        # ==========================================
        for a in abastecimentos:
            # Trava simples para evitar abastecimento clonado
            cursor.execute("SELECT id FROM fato_abastecimento WHERE id_veiculo = ? AND data_iso = ? AND hora = ? AND km_bomba = ?", 
                           (id_veiculo, a['dia'], a['hora'], a['km_bomba']))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO fato_abastecimento (id_motorista, id_veiculo, data_iso, hora, km_bomba, litros)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (id_motorista, id_veiculo, a['dia'], a['hora'], a['km_bomba'], a['litros']))

        # Se passou por todos os loops sem disparar nenhum erro, confirma o salvamento geral!
        conexao.commit()
        return True, "Jornada e Abastecimentos salvos com sucesso!"
    
    except Exception as e:
        conexao.rollback()
        return False, f"Erro ao salvar: {str(e)}"
    finally:
        conexao.close()

# Atualizando a busca para trazer os dois juntos
def buscar_dados_completos_periodo(id_motorista, id_veiculo, data_inicio, data_fim):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        # Puxa Viagens
        cursor.execute("SELECT * FROM fato_viagem WHERE id_motorista = ? AND id_veiculo = ? AND data_viagem BETWEEN ? AND ? ORDER BY data_viagem, hora_inicio", 
                       (id_motorista, id_veiculo, data_inicio, data_fim))
        viagens = [dict(v) for v in cursor.fetchall()]

        # Puxa Abastecimentos (CORREÇÃO: Agora exige o id_motorista também)
        cursor.execute("SELECT * FROM fato_abastecimento WHERE id_motorista = ? AND id_veiculo = ? AND data_iso BETWEEN ? AND ? ORDER BY data_iso, hora", 
                       (id_motorista, id_veiculo, data_inicio, data_fim))
        abastecimentos = [dict(a) for a in cursor.fetchall()]

        return viagens, abastecimentos
    finally:
        conexao.close()

# ==========================================
# FUNÇÕES DE DESENVOLVEDOR (DEV MODE)
# ==========================================

def buscar_ultima_jornada_dev():
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        cursor.execute("SELECT id_motorista, id_veiculo FROM fato_viagem ORDER BY id DESC LIMIT 1")
        ultimo = cursor.fetchone()
        
        if not ultimo:
            return None, None, []

        cursor.execute('''
            SELECT * FROM fato_viagem
            WHERE id_motorista = ? AND id_veiculo = ?
            ORDER BY id DESC LIMIT 10
        ''', (ultimo['id_motorista'], ultimo['id_veiculo']))
        
        viagens = cursor.fetchall()
        viagens_lista = [dict(v) for v in viagens]
        viagens_lista.reverse()
        
        return ultimo['id_motorista'], ultimo['id_veiculo'], viagens_lista
    finally:
        conexao.close()

def buscar_viagens_por_periodo(id_motorista, id_veiculo, data_inicio, data_fim):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        # ATUALIZAÇÃO: Como agora a data é ISO (YYYY-MM-DD), o BETWEEN funciona nativamente como texto
        cursor.execute('''
            SELECT * FROM fato_viagem
            WHERE id_motorista = ? 
              AND id_veiculo = ? 
              AND data_viagem BETWEEN ? AND ?
            ORDER BY data_viagem ASC, hora_inicio ASC
        ''', (id_motorista, id_veiculo, data_inicio, data_fim))
        
        viagens = cursor.fetchall()
        return [dict(v) for v in viagens]
    finally:
        conexao.close()

# ==========================================
# SCRIPT DE MIGRAÇÃO (RODAR APENAS UMA VEZ)
# ==========================================

def migrar_datas_antigas_para_fevereiro():
    """
    Procura viagens antigas que tinham apenas o dia (ex: '5' ou '14')
    e atualiza para o formato '2026-02-05' e '2026-02-14'.
    """
    conexao = obter_conexao()
    cursor = conexao.cursor()
    try:
        # Busca todas as datas que têm tamanho 1 ou 2 caracteres (ex: '1', '15')
        cursor.execute("SELECT id, data_viagem FROM fato_viagem WHERE length(data_viagem) <= 2")
        viagens = cursor.fetchall()
        
        if not viagens:
            print(" Nenhuma data antiga precisou ser migrada.")
            return

        for v in viagens:
            dia_str = str(v['data_viagem']).strip()
            # zfill(2) transforma '5' em '05'
            dia_formatado = dia_str.zfill(2)
            nova_data = f"2026-02-{dia_formatado}"
            
            cursor.execute("UPDATE fato_viagem SET data_viagem = ? WHERE id = ?", (nova_data, v['id']))
        
        conexao.commit()
        print(f"✅ Sucesso! {len(viagens)} viagens foram atualizadas para o formato de Fevereiro de 2026.")
    except Exception as e:
        conexao.rollback()
        print(f"❌ Erro na migração: {e}")
    finally:
        conexao.close()

# Se você rodar o database.py diretamente, ele executa a migração!
if __name__ == '__main__':
    migrar_datas_antigas_para_fevereiro()