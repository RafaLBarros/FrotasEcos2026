import sqlite3
from datetime import datetime, timedelta

def inicializar_banco():
    conexao = sqlite3.connect('ecos_database.db')
    cursor = conexao.cursor()

    cursor.execute('''
     CREATE TABLE IF NOT EXISTS fato_abastecimento (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         id_motorista INTEGER,
         id_veiculo INTEGER,
         data_iso TEXT,
         hora TEXT,
         km_bomba REAL,
         litros REAL,
         FOREIGN KEY (id_motorista) REFERENCES dim_motorista(id),
         FOREIGN KEY (id_veiculo) REFERENCES dim_veiculo(id)
        )
    ''')

    conexao.commit()
    conexao.close()

if __name__ == '__main__':
    inicializar_banco()