import pandas as pd
import io
import base64
from datetime import datetime

# Função auxiliar para transformar string em formato de tempo calculável
def parse_hora(hora_str):
    try:
        return datetime.strptime(hora_str, "%H:%M").time()
    except:
        return None

def rodar_auditoria_completa(dados_bdt, dados_combustivel):
    alertas = []
    logs_bdt = []
    km_total_declarado = 0
    km_total_nao_registrado = 0
    
    km_out_anterior = None
    
    # Parâmetros da ECOS
    HORA_COMERCIAL_INICIO = datetime.strptime("08:00", "%H:%M").time()
    HORA_COMERCIAL_FIM = datetime.strptime("18:00", "%H:%M").time()

    for i, linha in enumerate(dados_bdt):
        dia = int(linha['dia'])
        hora_in_str = linha['hora_in']
        hora_out_str = linha['hora_out']
        
        hora_in = parse_hora(hora_in_str)
        hora_out = parse_hora(hora_out_str)
        
        origem = linha['origem'].upper()
        destino = linha['destino'].upper()
        km_in = float(linha['km_in'])
        km_out = float(linha['km_out'])
        
        distancia = km_out - km_in
        km_total_declarado += distancia
        
        # --- REGRA 1: HORÁRIO ATÍPICO ---
        if hora_in and hora_in < HORA_COMERCIAL_INICIO:
            alertas.append(f"🟠 HORÁRIO ATÍPICO: Viagem no DIA {dia} de {origem} iniciou às {hora_in_str} (antes do horário comercial).")
        if hora_out and hora_out > HORA_COMERCIAL_FIM:
            alertas.append(f"🟠 HORÁRIO ATÍPICO: Viagem no DIA {dia} para {destino} encerrou às {hora_out_str} (após o horário comercial).")

        # --- REGRA 2: INCONSISTÊNCIA BÁSICA DE TEMPO E KM ---
        if km_out < km_in:
            alertas.append(f"🔴 ERRO: No DIA {dia}, KM Final ({km_out}) é menor que o KM Inicial ({km_in}).")
        if hora_in and hora_out and hora_out < hora_in:
            alertas.append(f"🔴 ERRO DE TEMPO: No DIA {dia}, a Hora Final ({hora_out_str}) é anterior à Hora Inicial ({hora_in_str}).")
            
        # --- REGRAS 3 e 4: SALTOS ---
        if km_out_anterior is not None:
            salto = km_in - km_out_anterior
            if salto > 0:
                km_total_nao_registrado += salto
                alertas.append(f"🟡 SALTO: Trecho não registrado de {salto:.1f}km antes da viagem do DIA {dia} ({km_out_anterior} -> {km_in}).")
                
                # Procura se ele abasteceu durante esse buraco negro de KM
                for comb in dados_combustivel:
                    km_bomba = float(comb['km_bomba'])
                    if km_out_anterior < km_bomba < km_in:
                        hora_abast = comb.get('hora', 'Hora Desconhecida')
                        alertas.append(f"🚨 FRAUDE GRAVE: Abastecimento de {comb['litros']}L no DIA {comb['dia']} às {hora_abast} (KM {km_bomba}) ocorreu durante o salto não registrado de {salto:.1f}km!")

        # --- REGRA 5: A FRAUDE DO ESPAÇO-TEMPO (A MAIS PODEROSA) ---
        for comb in dados_combustivel:
            dia_comb = int(comb['dia'])
            km_bomba = float(comb['km_bomba'])
            hora_comb = parse_hora(comb['hora'])
            
            # Se o abastecimento foi no mesmo dia e o hodômetro bate com o da viagem atual...
            if dia_comb == dia and km_in <= km_bomba <= km_out:
                if hora_comb and hora_in and hora_out:
                    # Mas a hora do posto não está entre a hora que ele iniciou e terminou a corrida
                    if not (hora_in <= hora_comb <= hora_out):
                        alertas.append(f"🚨 CONTRADIÇÃO ESPAÇO-TEMPO: No DIA {dia}, a viagem das {hora_in_str}-{hora_out_str} cobriu os KMs {km_in}-{km_out}. O abastecimento no KM {km_bomba} bate com o trajeto, mas ocorreu às {comb['hora']}, que está FORA da janela de tempo declarada!")

            # Verifica viagem no tempo normal (KM do passado sendo maior que o de hoje)
            if dia_comb < dia and km_bomba > km_in:
                alertas.append(f"🚨 INCONSISTÊNCIA DE HODÔMETRO: BDT iniciou no DIA {dia} em {km_in}, mas um abastecimento em dia anterior (Dia {dia_comb}) já marcava {km_bomba}.")

        km_out_anterior = km_out
        
        logs_bdt.append({
            "Dia": dia, "Hora In": hora_in_str, "Hora Fim": hora_out_str,
            "Origem": origem, "Destino": destino, 
            "KM Inicial": km_in, "KM Final": km_out, "Distância (km)": distancia
        })

    df_bdt = pd.DataFrame(logs_bdt)
    df_comb = pd.DataFrame(dados_combustivel)
    df_alertas = pd.DataFrame({"Alertas Encontrados": alertas})
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_bdt.to_excel(writer, sheet_name='BDT Validado', index=False)
        if not df_comb.empty:
            df_comb.to_excel(writer, sheet_name='Abastecimentos', index=False)
        df_alertas.to_excel(writer, sheet_name='Alertas', index=False)
    
    excel_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return {
        "status": "sucesso",
        "km_declarado": km_total_declarado,
        "km_nao_registrado": km_total_nao_registrado,
        "total_rodado": km_total_declarado + km_total_nao_registrado,
        "alertas": alertas,
        "excel_b64": excel_b64
    }