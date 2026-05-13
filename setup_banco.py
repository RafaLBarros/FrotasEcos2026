import sqlite3

def inicializar_banco():
    print("Iniciando a construção do banco de dados ECOS...")
    conexao = sqlite3.connect('ecos_database.db')
    cursor = conexao.cursor()

    # =========================================================
    # 1. CRIAÇÃO DAS TABELAS DE DIMENSÃO (CADASTROS)
    # =========================================================
    
    # Tabela de Motoristas (Quem)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_motorista (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            matricula TEXT UNIQUE,
            status TEXT DEFAULT 'ATIVO'
        )
    ''')

    # Tabela de Veículos (O Que) - ATUALIZADA COM DADOS DO CRLV
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dim_veiculo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT UNIQUE NOT NULL,
            marca_modelo TEXT NOT NULL,
            ano_modelo INTEGER,
            tipo_combustivel TEXT,
            especie_capacidade TEXT,
            proprietario_locadora TEXT,
            renavam TEXT,
            status TEXT DEFAULT 'ATIVO'
        )
    ''')

    # =========================================================
    # 2. CRIAÇÃO DA TABELA FATO (O EVENTO / A VIAGEM)
    # =========================================================
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fato_viagem (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_motorista INTEGER,
            id_veiculo INTEGER,
            data_viagem TEXT,
            hora_inicio TEXT,
            hora_fim TEXT,
            origem TEXT,
            destino TEXT,
            km_inicial REAL,
            km_final REAL,
            distancia_percorrida REAL,
            km_maps_opcional REAL,
            alertas_gerados TEXT,
            FOREIGN KEY (id_motorista) REFERENCES dim_motorista(id),
            FOREIGN KEY (id_veiculo) REFERENCES dim_veiculo(id)
        )
    ''')

    # =========================================================
    # 3. INJETANDO DADOS DE TESTE (Baseado no seu documento)
    # =========================================================
    
    # Inserindo Motoristas se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM dim_motorista")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO dim_motorista (nome, matricula) VALUES ('Rafael Lopes', 'MAT-001')")
        cursor.execute("INSERT INTO dim_motorista (nome, matricula) VALUES ('Miguel (Motorista Van)', 'MAT-002')")
        print("Motoristas de teste inseridos.")

    # Inserindo Veículos se a tabela estiver vazia (Usando sua Renault Master e o Argo que você mencionou antes)
    cursor.execute("SELECT COUNT(*) FROM dim_veiculo")
    if cursor.fetchone()[0] == 0:
        # A Van do CRLV
        cursor.execute('''
            INSERT INTO dim_veiculo 
            (placa, marca_modelo, ano_modelo, tipo_combustivel, especie_capacidade, proprietario_locadora, renavam) 
            VALUES 
            ('FUC0328', 'RENAULT / MASTER MART L3', 2015, 'DIESEL', 'MICROONIBUS - 15P', 'BIGVANS COMERCIO LTDA', '01014785526')
        ''')
        # O carro da ECOS
        cursor.execute('''
            INSERT INTO dim_veiculo 
            (placa, marca_modelo, ano_modelo, tipo_combustivel, especie_capacidade, proprietario_locadora, renavam) 
            VALUES 
            ('ECO2026', 'FIAT / ARGO 1.0', 2018, 'FLEX', 'PASSEIO - 5P', 'FROTA PROPRIA', '00000000000')
        ''')
        print("Veículos de teste inseridos.")

    # Salva e fecha a conexão
    conexao.commit()
    conexao.close()
    
    print("Banco de dados pronto para uso! Arquivo 'ecos_database.db' gerado com sucesso.")

if __name__ == '__main__':
    inicializar_banco()