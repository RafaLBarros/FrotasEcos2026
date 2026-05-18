import sqlite3

def limpar_dados_de_teste():
    conexao = sqlite3.connect('ecos_database.db')
    cursor = conexao.cursor()

    try:
        # 1. Apaga todas as viagens e abastecimentos
        cursor.execute("DELETE FROM fato_viagem")
        cursor.execute("DELETE FROM fato_abastecimento")
        
        # 2. Reseta o contador de IDs (para que a próxima viagem volte a ser a de ID 1)
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='fato_viagem'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='fato_abastecimento'")

        conexao.commit()
        print("✅ Limpeza concluída com sucesso!")
        print("🧹 Todas as viagens e abastecimentos foram apagados.")
        print("👤 Seus Motoristas e Veículos foram mantidos intactos.")
        
    except Exception as e:
        conexao.rollback()
        print(f"❌ Ocorreu um erro: {e}")
    finally:
        conexao.close()

if __name__ == '__main__':
    # Adicionando uma travinha de segurança para evitar acidentes no futuro
    confirmacao = input("⚠️ Tem certeza que deseja APAGAR todas as viagens e abastecimentos? (S/N): ")
    if confirmacao.strip().upper() == 'S':
        limpar_dados_de_teste()
    else:
        print("Operação cancelada.")